import { useEffect, useState } from "react";
import { api, Import, ImportStatus } from "../lib/api";
import { StatusStamp, importStatusStamp } from "../components/StatusStamp";
import { CatalogCard } from "../components/CatalogCard";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { Button } from "../components/Button";
import { Input } from "../components/Input";

export default function Dashboard() {
  const PER_PAGE = 50;
  const STATUS_ORDER: Record<string, number> = { importing: 0, pending: 1, needs_review: 2, failed: 3, imported: 4 };
  const [imports, setImports] = useState<Import[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [form, setForm] = useState({ path: "", category: "audiobook", author: "", title: "" });
  const [submitting, setSubmitting] = useState(false);
  const [retrying, setRetrying] = useState<number | null>(null);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    api.listImports().then(data => { setImports(data); setPage(1); }).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleScan = async () => {
    setScanning(true);
    try {
      await api.triggerScan();
      setTimeout(() => { load(); setScanning(false); }, 2000);
    } catch {
      setScanning(false);
    }
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

  const counts = imports.reduce((acc, i) => {
    acc[i.status] = (acc[i.status] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.manualImport({
        path: form.path,
        category: form.category as "audiobook" | "ebook",
        author: form.author || undefined,
        title: form.title || undefined,
      });
      setShowManual(false);
      setForm({ path: "", category: "audiobook", author: "", title: "" });
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>Import History</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <Button onClick={handleScan} disabled={scanning}>
            {scanning ? "Scanning..." : "Scan now"}
          </Button>
          <Button onClick={load}>Refresh</Button>
          <Button variant="primary" onClick={() => setShowManual(true)}>+ Add Book</Button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap" }}>
        {(Object.entries(counts) as [ImportStatus, number][]).map(([status, count]) => {
          const stamp = importStatusStamp(status);
          return (
            <CatalogCard key={status} tone={stamp.tone} compact>
              <div className="mono" style={{ fontSize: 20, fontWeight: 600 }}>{count}</div>
              <StatusStamp {...stamp} />
            </CatalogCard>
          );
        })}
      </div>

      {showManual && (
        <CatalogCard tone="brass">
          <h3 className="catalog-card__title" style={{ fontSize: 16, marginBottom: 16 }}>Add Book Manually</h3>
          <form onSubmit={handleManualSubmit}>
            <div style={{ display: "grid", gap: 12 }}>
              <Input required placeholder="File or folder path" value={form.path} onChange={e => setForm(f => ({ ...f, path: e.target.value }))} />
              <select className="input" value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}>
                <option value="audiobook">Audiobook</option>
                <option value="ebook">Ebook</option>
              </select>
              <Input placeholder="Author (optional — series data still looked up)" value={form.author} onChange={e => setForm(f => ({ ...f, author: e.target.value }))} />
              <Input placeholder="Title (optional)" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
              {error && <div style={{ color: "var(--clay)", fontSize: 13 }}>{error}</div>}
              <div style={{ display: "flex", gap: 8 }}>
                <Button type="submit" variant="success" disabled={submitting}>
                  {submitting ? "Adding..." : "Add Book"}
                </Button>
                <Button type="button" onClick={() => setShowManual(false)}>Cancel</Button>
              </div>
            </div>
          </form>
        </CatalogCard>
      )}

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", marginTop: showManual ? 24 : 0 }}>
        {(["all", "importing", "pending", "needs_review", "failed", "imported"] as const).map(s => (
          <Button
            key={s}
            size="sm"
            variant={statusFilter === s ? "primary" : "secondary"}
            onClick={() => { setStatusFilter(s); setPage(1); }}
          >
            {s === "all" ? "All" : s.replace("_", " ")}
            {s !== "all" && counts[s] ? ` (${counts[s]})` : ""}
          </Button>
        ))}
      </div>

      {loading ? <div style={{ color: "var(--text-muted)" }}>Loading...</div> : (() => {
        const filtered = statusFilter === "all" ? imports : imports.filter(i => i.status === statusFilter);
        const sorted = [...filtered].sort((a, b) => (STATUS_ORDER[a.status] ?? 5) - (STATUS_ORDER[b.status] ?? 5));
        const totalPages = Math.max(1, Math.ceil(sorted.length / PER_PAGE));
        const pageImports = sorted.slice((page - 1) * PER_PAGE, page * PER_PAGE);
        return (
          <div style={{ display: "grid", gap: 10 }}>
            {pageImports.length === 0 && (
              <CatalogCard>
                <div style={{ textAlign: "center", color: "var(--text-muted)", padding: 12 }}>No imports yet</div>
              </CatalogCard>
            )}
            {pageImports.map(imp => {
              const stamp = importStatusStamp(imp.status);
              return (
                <CatalogCard key={imp.id} tone={stamp.tone}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                    <div style={{ minWidth: 0 }}>
                      <div className="catalog-card__title" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={imp.name}>
                        {imp.resolved_title || imp.name}
                      </div>
                      <div className="catalog-card__meta">
                        {imp.category}
                        {imp.resolved_author ? ` · ${imp.resolved_author}` : ""}
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                      <StatusStamp {...stamp} />
                      {(imp.status === "failed" || imp.status === "needs_review") && (
                        <Button size="sm" onClick={() => handleRetry(imp.id)} disabled={retrying === imp.id}>
                          {retrying === imp.id ? "…" : "Retry"}
                        </Button>
                      )}
                    </div>
                  </div>

                  <div className="catalog-card__strip">
                    <span className="mono">{new Date(imp.created_at).toLocaleDateString()}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                      {imp.isbn && <span className="mono">{imp.isbn}</span>}
                      {imp.metadata_confidence != null && (
                        <div style={{ width: 100 }}>
                          <ConfidenceBar value={imp.metadata_confidence} />
                        </div>
                      )}
                    </div>
                  </div>

                  {imp.status === "failed" && imp.error_message && (
                    <div style={{ marginTop: 8, fontSize: 12, color: "var(--clay)" }}>{imp.error_message}</div>
                  )}
                </CatalogCard>
              );
            })}

            {totalPages > 1 && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 4px" }}>
                <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
                  {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, sorted.length)} of {sorted.length}
                </span>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  <Button size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>←</Button>
                  <span style={{ fontSize: 13, color: "var(--text-muted)", padding: "4px 6px" }}>Page {page} of {totalPages}</span>
                  <Button size="sm" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>→</Button>
                </div>
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}
