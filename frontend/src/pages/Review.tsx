import { useEffect, useMemo, useRef, useState } from "react";
import { api, Import, Candidate } from "../lib/api";
import { useIsMobile } from "../lib/useIsMobile";
import { StatusStamp, importStatusStamp } from "../components/StatusStamp";
import { CatalogCard } from "../components/CatalogCard";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { Button } from "../components/Button";
import { Input } from "../components/Input";

function useCandidates(json: string | null): Candidate[] {
  return useMemo(() => (json ? JSON.parse(json) : []), [json]);
}

export default function Review() {
  const isMobile = useIsMobile();
  const [imports, setImports] = useState<Import[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<Import | null>(null);
  const [form, setForm] = useState({ author: "", title: "", series: "", series_seq: "" });
  const [submitting, setSubmitting] = useState(false);
  const [retrying, setRetrying] = useState<number | null>(null);
  const [error, setError] = useState("");

  const activeRef = useRef(active);
  activeRef.current = active;

  const load = (silent = false) => {
    if (!silent) setLoading(true);
    api.listImports("needs_review").then(data => {
      setImports(data);
      // Refresh the active item in place if the modal is open
      if (activeRef.current) {
        const updated = data.find(i => i.id === activeRef.current!.id);
        if (updated) setActive(updated);
        else setActive(null);
      }
    }).finally(() => { if (!silent) setLoading(false); });
  };

  useEffect(() => {
    load();
    const timer = setInterval(() => load(true), 5000);
    return () => clearInterval(timer);
  }, []);

  const openReview = (imp: Import) => {
    setActive(imp);
    setForm({ author: imp.resolved_author || "", title: imp.resolved_title || "", series: imp.resolved_series || "", series_seq: imp.resolved_series_seq || "" });
    setError("");
  };

  const selectCandidate = (c: Candidate) => {
    setForm({ author: c.author, title: c.title, series: c.series, series_seq: c.series_seq });
  };

  const handleRetry = async (id: number) => {
    setRetrying(id);
    try {
      await api.retryImport(id);
      load();
    } finally {
      setRetrying(null);
    }
  };

  const handleApprove = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!active) return;
    setSubmitting(true);
    setError("");
    try {
      await api.approveImport(active.id, form);
      setActive(null);
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 24 }}>Needs Review ({imports.length})</h1>

      {loading ? <div style={{ color: "var(--text-muted)" }}>Loading...</div> : imports.length === 0 ? (
        <CatalogCard><div style={{ color: "var(--text-muted)", padding: 12, textAlign: "center" }}>Nothing to review</div></CatalogCard>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {imports.map(imp => (
            <ReviewCard
              key={imp.id}
              imp={imp}
              retrying={retrying === imp.id}
              onReview={() => openReview(imp)}
              onRetry={() => handleRetry(imp.id)}
            />
          ))}
        </div>
      )}

      {active && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
          <div className="catalog-card" style={{
            borderLeft: "none", width: isMobile ? "100%" : 520, height: isMobile ? "100%" : undefined,
            maxHeight: isMobile ? "100%" : "90vh", overflow: "auto", padding: isMobile ? 20 : 32,
            boxShadow: "0 8px 32px rgba(0,0,0,.3)", borderRadius: isMobile ? 0 : "var(--radius-card)",
          }}>
            <h2 className="catalog-card__title" style={{ fontSize: 20, marginBottom: 4 }}>Resolve Metadata</h2>
            <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 20 }}>{active.name}</div>

            <CandidateList json={active.candidates_json} onSelect={selectCandidate} form={form} />

            <form onSubmit={handleApprove}>
              <div style={{ display: "grid", gap: 10 }}>
                <Input required placeholder="Author" value={form.author} onChange={e => setForm(f => ({ ...f, author: e.target.value }))} />
                <Input required placeholder="Title" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
                <Input placeholder="Series (optional)" value={form.series} onChange={e => setForm(f => ({ ...f, series: e.target.value }))} />
                <Input placeholder="Series # (optional)" value={form.series_seq} onChange={e => setForm(f => ({ ...f, series_seq: e.target.value }))} />
                {error && <div style={{ color: "var(--clay)", fontSize: 13 }}>{error}</div>}
                <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  <Button type="submit" variant="success" disabled={submitting}>
                    {submitting ? "Importing..." : "Confirm & Import"}
                  </Button>
                  <Button type="button" onClick={() => setActive(null)}>Cancel</Button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewCard({ imp, retrying, onReview, onRetry }: {
  imp: Import; retrying: boolean; onReview: () => void; onRetry: () => void;
}) {
  const candidates = useCandidates(imp.candidates_json);
  const stamp = importStatusStamp(imp.status);

  return (
    <CatalogCard tone={stamp.tone}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div style={{ minWidth: 0 }}>
          <div className="catalog-card__title">{imp.name}</div>
          <div className="catalog-card__meta">{imp.category} · {imp.content_path}</div>
          {imp.metadata_confidence != null && (
            <div style={{ marginTop: 8, maxWidth: 220 }}>
              <ConfidenceBar value={imp.metadata_confidence} />
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <Button size="sm" variant="primary" onClick={onReview}>Review</Button>
          <Button size="sm" onClick={onRetry} disabled={retrying}>{retrying ? "…" : "Retry"}</Button>
        </div>
      </div>

      {candidates.length > 0 && (
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {candidates.map((c, i) => (
            <CatalogCard key={i} compact tone="slate">
              <strong>{c.title}</strong> — {c.author}
              <span className="mono" style={{ color: "var(--text-muted)", marginLeft: 6 }}>{Math.round(c.score * 100)}%</span>
            </CatalogCard>
          ))}
        </div>
      )}
    </CatalogCard>
  );
}

function CandidateList({ json, onSelect, form }: {
  json: string | null; onSelect: (c: Candidate) => void; form: { author: string; title: string };
}) {
  const candidates = useCandidates(json);
  if (candidates.length === 0) return null;

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Candidates</div>
      <div style={{ display: "grid", gap: 6 }}>
        {candidates.map((c, i) => {
          const selected = c.title === form.title && c.author === form.author;
          return (
            <CatalogCard key={i} compact tone="brass" selected={selected} onClick={() => onSelect(c)}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
                <span>
                  <strong>{c.title}</strong> — {c.author}
                  {c.series && <span style={{ color: "var(--text-muted)" }}> ({c.series} #{c.series_seq})</span>}
                  <span className="mono" style={{ color: "var(--text-muted)", fontSize: 11, marginLeft: 6 }}>[{c.source}/{c.match_method}]</span>
                </span>
                <span className="mono" style={{ color: "var(--text-muted)", flexShrink: 0 }}>{Math.round(c.score * 100)}%</span>
              </div>
            </CatalogCard>
          );
        })}
      </div>
    </div>
  );
}
