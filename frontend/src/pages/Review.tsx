import { useEffect, useState } from "react";
import { api, Import, Candidate } from "../lib/api";
import { useTheme } from "../lib/ThemeContext";

export default function Review() {
  const { tokens } = useTheme();
  const [imports, setImports] = useState<Import[]>([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState<Import | null>(null);
  const [form, setForm] = useState({ author: "", title: "", series: "", series_seq: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    api.listImports("needs_review").then(setImports).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const openReview = (imp: Import) => {
    setActive(imp);
    setForm({ author: imp.resolved_author || "", title: imp.resolved_title || "", series: imp.resolved_series || "", series_seq: imp.resolved_series_seq || "" });
    setError("");
  };

  const selectCandidate = (c: Candidate) => {
    setForm({ author: c.author, title: c.title, series: c.series, series_seq: c.series_seq });
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

  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "8px 12px", border: `1px solid ${tokens.inputBorder}`,
    borderRadius: 6, fontSize: 14, boxSizing: "border-box",
    background: tokens.surface, color: tokens.text,
  };

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 24, color: tokens.text }}>Needs Review ({imports.length})</h1>

      {loading ? <div style={{ color: tokens.textMuted }}>Loading...</div> : imports.length === 0 ? (
        <div style={{ color: tokens.textMuted, padding: 32, textAlign: "center" }}>Nothing to review</div>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {imports.map(imp => {
            const candidates: Candidate[] = imp.candidates_json ? JSON.parse(imp.candidates_json) : [];
            return (
              <div key={imp.id} style={{ background: tokens.surface, borderRadius: 8, padding: 20, boxShadow: tokens.shadow }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: 4, color: tokens.text }}>{imp.name}</div>
                    <div style={{ fontSize: 12, color: tokens.textMuted }}>{imp.category} · {imp.content_path}</div>
                    {imp.metadata_confidence != null && (
                      <div style={{ fontSize: 12, color: "#fd7e14", marginTop: 4 }}>
                        Best match confidence: {Math.round(imp.metadata_confidence * 100)}%
                      </div>
                    )}
                  </div>
                  <button onClick={() => openReview(imp)} style={btnStyle("#0d6efd")}>Review</button>
                </div>

                {candidates.length > 0 && (
                  <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {candidates.map((c, i) => (
                      <div key={i} style={{ background: tokens.surfaceHover, border: `1px solid ${tokens.border}`, borderRadius: 6, padding: "6px 10px", fontSize: 12, color: tokens.text }}>
                        <strong>{c.title}</strong> — {c.author}
                        <span style={{ color: tokens.textMuted, marginLeft: 6 }}>{Math.round(c.score * 100)}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {active && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
          <div style={{ background: tokens.surface, borderRadius: 10, padding: 32, width: 520, maxHeight: "90vh", overflow: "auto", boxShadow: "0 8px 32px rgba(0,0,0,.3)" }}>
            <h2 style={{ margin: "0 0 8px", color: tokens.text }}>Resolve Metadata</h2>
            <div style={{ fontSize: 13, color: tokens.textMuted, marginBottom: 20 }}>{active.name}</div>

            {active.candidates_json && JSON.parse(active.candidates_json).length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: tokens.text }}>Candidates</div>
                {(JSON.parse(active.candidates_json) as Candidate[]).map((c, i) => (
                  <div
                    key={i}
                    onClick={() => selectCandidate(c)}
                    style={{ border: `1px solid ${tokens.border}`, borderRadius: 6, padding: "10px 12px", marginBottom: 6, cursor: "pointer", fontSize: 13, color: tokens.text, background: tokens.surfaceHover }}
                  >
                    <strong>{c.title}</strong> — {c.author}
                    {c.series && <span style={{ color: tokens.textMuted }}> ({c.series} #{c.series_seq})</span>}
                    <span style={{ float: "right", color: tokens.textMuted }}>{Math.round(c.score * 100)}%</span>
                  </div>
                ))}
              </div>
            )}

            <form onSubmit={handleApprove}>
              <div style={{ display: "grid", gap: 10 }}>
                <input required placeholder="Author" value={form.author} onChange={e => setForm(f => ({ ...f, author: e.target.value }))} style={inputStyle} />
                <input required placeholder="Title" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} style={inputStyle} />
                <input placeholder="Series (optional)" value={form.series} onChange={e => setForm(f => ({ ...f, series: e.target.value }))} style={inputStyle} />
                <input placeholder="Series # (optional)" value={form.series_seq} onChange={e => setForm(f => ({ ...f, series_seq: e.target.value }))} style={inputStyle} />
                {error && <div style={{ color: "#dc3545", fontSize: 13 }}>{error}</div>}
                <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  <button type="submit" disabled={submitting} style={btnStyle("#198754")}>
                    {submitting ? "Importing..." : "Confirm & Import"}
                  </button>
                  <button type="button" onClick={() => setActive(null)} style={btnStyle("#6c757d")}>Cancel</button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

const btnStyle = (bg: string): React.CSSProperties => ({
  background: bg, color: "#fff", border: "none", borderRadius: 6,
  padding: "8px 16px", cursor: "pointer", fontSize: 14,
});
