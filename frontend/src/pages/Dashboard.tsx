import { useEffect, useState } from "react";
import { api, Import, ImportStatus } from "../lib/api";
import { useTheme } from "../lib/ThemeContext";

const STATUS_COLORS: Record<ImportStatus, string> = {
  pending: "#6c757d",
  importing: "#0d6efd",
  imported: "#198754",
  needs_review: "#fd7e14",
  failed: "#dc3545",
};

function StatusBadge({ status }: { status: ImportStatus }) {
  return (
    <span style={{ background: STATUS_COLORS[status], color: "#fff", padding: "2px 8px", borderRadius: 99, fontSize: 12, fontWeight: 600 }}>
      {status.replace("_", " ")}
    </span>
  );
}

export default function Dashboard() {
  const { tokens } = useTheme();
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

  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "8px 12px", border: `1px solid ${tokens.inputBorder}`,
    borderRadius: 6, fontSize: 14, boxSizing: "border-box",
    background: tokens.surface, color: tokens.text,
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ margin: 0, fontSize: 24, color: tokens.text }}>Import History</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleScan} disabled={scanning} style={{ background: "none", border: `1px solid ${tokens.border}`, borderRadius: 6, padding: "7px 14px", cursor: "pointer", fontSize: 13, color: tokens.textMuted }}>
            {scanning ? "Scanning..." : "Scan now"}
          </button>
          <button onClick={load} style={{ background: "none", border: `1px solid ${tokens.border}`, borderRadius: 6, padding: "7px 14px", cursor: "pointer", fontSize: 13, color: tokens.textMuted }}>
            Refresh
          </button>
          <button onClick={() => setShowManual(true)} style={{ background: "#0d6efd", color: "#fff", border: "none", borderRadius: 6, padding: "8px 16px", cursor: "pointer" }}>
            + Add Book
          </button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
        {(Object.entries(counts) as [ImportStatus, number][]).map(([status, count]) => (
          <div key={status} style={{ background: tokens.surface, borderRadius: 8, padding: "12px 20px", boxShadow: tokens.shadow }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: tokens.text }}>{count}</div>
            <StatusBadge status={status} />
          </div>
        ))}
      </div>

      {showManual && (
        <div style={{ background: tokens.surface, borderRadius: 8, padding: 24, marginBottom: 24, boxShadow: tokens.shadow }}>
          <h3 style={{ margin: "0 0 16px", color: tokens.text }}>Add Book Manually</h3>
          <form onSubmit={handleManualSubmit}>
            <div style={{ display: "grid", gap: 12 }}>
              <input required placeholder="File or folder path" value={form.path} onChange={e => setForm(f => ({ ...f, path: e.target.value }))} style={inputStyle} />
              <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} style={inputStyle}>
                <option value="audiobook">Audiobook</option>
                <option value="ebook">Ebook</option>
              </select>
              <input placeholder="Author (optional — series data still looked up)" value={form.author} onChange={e => setForm(f => ({ ...f, author: e.target.value }))} style={inputStyle} />
              <input placeholder="Title (optional)" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} style={inputStyle} />
              {error && <div style={{ color: "#dc3545", fontSize: 13 }}>{error}</div>}
              <div style={{ display: "flex", gap: 8 }}>
                <button type="submit" disabled={submitting} style={{ background: "#198754", color: "#fff", border: "none", borderRadius: 6, padding: "8px 16px", cursor: "pointer" }}>
                  {submitting ? "Adding..." : "Add Book"}
                </button>
                <button type="button" onClick={() => setShowManual(false)} style={{ background: "#6c757d", color: "#fff", border: "none", borderRadius: 6, padding: "8px 16px", cursor: "pointer" }}>
                  Cancel
                </button>
              </div>
            </div>
          </form>
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {(["all", "importing", "pending", "needs_review", "failed", "imported"] as const).map(s => (
          <button
            key={s}
            onClick={() => { setStatusFilter(s); setPage(1); }}
            style={{
              background: statusFilter === s ? "#0d6efd" : "none",
              color: statusFilter === s ? "#fff" : tokens.textMuted,
              border: `1px solid ${statusFilter === s ? "#0d6efd" : tokens.border}`,
              borderRadius: 6, padding: "5px 12px", cursor: "pointer", fontSize: 13,
            }}
          >
            {s === "all" ? "All" : s.replace("_", " ")}
            {s !== "all" && counts[s] ? ` (${counts[s]})` : ""}
          </button>
        ))}
      </div>

      {loading ? <div style={{ color: tokens.textMuted }}>Loading...</div> : (() => {
        const filtered = statusFilter === "all" ? imports : imports.filter(i => i.status === statusFilter);
        const sorted = [...filtered].sort((a, b) => (STATUS_ORDER[a.status] ?? 5) - (STATUS_ORDER[b.status] ?? 5));
        const totalPages = Math.max(1, Math.ceil(sorted.length / PER_PAGE));
        const pageImports = sorted.slice((page - 1) * PER_PAGE, page * PER_PAGE);
        return (
        <div style={{ background: tokens.surface, borderRadius: 8, boxShadow: tokens.shadow, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14, minWidth: 680 }}>
            <thead>
              <tr style={{ background: tokens.surfaceHover }}>
                {["Name", "Category", "Status", "Author", "Title", "Confidence", "Added", ""].map(h => (
                  <th key={h} style={{ padding: "10px 14px", textAlign: "left", fontWeight: 600, fontSize: 12, color: tokens.textMuted }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageImports.map((imp, i) => (
                <>
                  <tr key={imp.id} style={{ borderTop: `1px solid ${tokens.border}`, background: i % 2 === 0 ? tokens.surface : tokens.surfaceHover }}>
                    <td style={{ padding: "10px 14px", maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: tokens.text }} title={imp.name}>{imp.name}</td>
                    <td style={{ padding: "10px 14px", color: tokens.textMuted }}>{imp.category}</td>
                    <td style={{ padding: "10px 14px" }}><StatusBadge status={imp.status} /></td>
                    <td style={{ padding: "10px 14px", color: tokens.text }}>{imp.resolved_author || "—"}</td>
                    <td style={{ padding: "10px 14px", color: tokens.text }}>{imp.resolved_title || "—"}</td>
                    <td style={{ padding: "10px 14px", color: tokens.text }}>
                      {imp.metadata_confidence != null ? `${Math.round(imp.metadata_confidence * 100)}%` : "—"}
                    </td>
                    <td style={{ padding: "10px 14px", color: tokens.textMuted, fontSize: 12 }}>
                      {new Date(imp.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: "10px 14px" }}>
                      {(imp.status === "failed" || imp.status === "needs_review") && (
                        <button
                          onClick={() => handleRetry(imp.id)}
                          disabled={retrying === imp.id}
                          style={{ background: "none", border: `1px solid ${tokens.border}`, borderRadius: 5, padding: "4px 10px", cursor: "pointer", fontSize: 12, color: tokens.textMuted }}
                        >
                          {retrying === imp.id ? "…" : "Retry"}
                        </button>
                      )}
                    </td>
                  </tr>
                  {imp.status === "failed" && imp.error_message && (
                    <tr key={`${imp.id}-err`} style={{ background: i % 2 === 0 ? tokens.surface : tokens.surfaceHover }}>
                      <td colSpan={8} style={{ padding: "0 14px 10px", fontSize: 12, color: "#dc3545" }}>
                        {imp.error_message}
                      </td>
                    </tr>
                  )}
                </>
              ))}
              {pageImports.length === 0 && (
                <tr><td colSpan={8} style={{ padding: 32, textAlign: "center", color: tokens.textMuted }}>No imports yet</td></tr>
              )}
            </tbody>
          </table>
          </div>
          {totalPages > 1 && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 16px", borderTop: `1px solid ${tokens.border}` }}>
              <span style={{ fontSize: 13, color: tokens.textMuted }}>
                {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, sorted.length)} of {sorted.length}
              </span>
              <div style={{ display: "flex", gap: 6 }}>
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} style={{ background: "none", border: `1px solid ${tokens.border}`, borderRadius: 5, padding: "4px 10px", cursor: page === 1 ? "default" : "pointer", fontSize: 13, color: page === 1 ? tokens.textMuted : tokens.text, opacity: page === 1 ? 0.4 : 1 }}>←</button>
                <span style={{ fontSize: 13, color: tokens.textMuted, padding: "4px 6px" }}>Page {page} of {totalPages}</span>
                <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={{ background: "none", border: `1px solid ${tokens.border}`, borderRadius: 5, padding: "4px 10px", cursor: page === totalPages ? "default" : "pointer", fontSize: 13, color: page === totalPages ? tokens.textMuted : tokens.text, opacity: page === totalPages ? 0.4 : 1 }}>→</button>
              </div>
            </div>
          )}
        </div>
        );
      })()}
    </div>
  );
}
