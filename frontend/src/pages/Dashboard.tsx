import { useEffect, useState } from "react";
import { api, Import, ImportStatus } from "../lib/api";

const STATUS_COLORS: Record<ImportStatus, string> = {
  pending: "#6c757d",
  importing: "#0d6efd",
  imported: "#198754",
  needs_review: "#fd7e14",
  failed: "#dc3545",
};

function StatusBadge({ status }: { status: ImportStatus }) {
  return (
    <span
      style={{
        background: STATUS_COLORS[status],
        color: "#fff",
        padding: "2px 8px",
        borderRadius: 99,
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {status.replace("_", " ")}
    </span>
  );
}

export default function Dashboard() {
  const [imports, setImports] = useState<Import[]>([]);
  const [loading, setLoading] = useState(true);
  const [showManual, setShowManual] = useState(false);
  const [form, setForm] = useState({ path: "", category: "audiobook", author: "", title: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    api.listImports().then(setImports).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

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
        <button
          onClick={() => setShowManual(true)}
          style={{ background: "#0d6efd", color: "#fff", border: "none", borderRadius: 6, padding: "8px 16px", cursor: "pointer" }}
        >
          + Add Book
        </button>
      </div>

      <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
        {(Object.entries(counts) as [ImportStatus, number][]).map(([status, count]) => (
          <div key={status} style={{ background: "#fff", borderRadius: 8, padding: "12px 20px", boxShadow: "0 1px 3px rgba(0,0,0,.1)" }}>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{count}</div>
            <StatusBadge status={status} />
          </div>
        ))}
      </div>

      {showManual && (
        <div style={{ background: "#fff", borderRadius: 8, padding: 24, marginBottom: 24, boxShadow: "0 1px 3px rgba(0,0,0,.1)" }}>
          <h3 style={{ margin: "0 0 16px" }}>Add Book Manually</h3>
          <form onSubmit={handleManualSubmit}>
            <div style={{ display: "grid", gap: 12 }}>
              <input required placeholder="File or folder path" value={form.path} onChange={e => setForm(f => ({ ...f, path: e.target.value }))} style={inputStyle} />
              <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} style={inputStyle}>
                <option value="audiobook">Audiobook</option>
                <option value="ebook">Ebook</option>
              </select>
              <input placeholder="Author (optional — skips metadata lookup)" value={form.author} onChange={e => setForm(f => ({ ...f, author: e.target.value }))} style={inputStyle} />
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

      {loading ? (
        <div>Loading...</div>
      ) : (
        <div style={{ background: "#fff", borderRadius: 8, boxShadow: "0 1px 3px rgba(0,0,0,.1)", overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ background: "#f1f3f5" }}>
                {["Name", "Category", "Status", "Author", "Title", "Confidence", "Added"].map(h => (
                  <th key={h} style={{ padding: "10px 14px", textAlign: "left", fontWeight: 600, fontSize: 12, color: "#495057" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {imports.map((imp, i) => (
                <tr key={imp.id} style={{ borderTop: "1px solid #dee2e6", background: i % 2 === 0 ? "#fff" : "#fafafa" }}>
                  <td style={{ padding: "10px 14px", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={imp.name}>{imp.name}</td>
                  <td style={{ padding: "10px 14px" }}>{imp.category}</td>
                  <td style={{ padding: "10px 14px" }}><StatusBadge status={imp.status} /></td>
                  <td style={{ padding: "10px 14px" }}>{imp.resolved_author || "—"}</td>
                  <td style={{ padding: "10px 14px" }}>{imp.resolved_title || "—"}</td>
                  <td style={{ padding: "10px 14px" }}>
                    {imp.metadata_confidence != null ? `${Math.round(imp.metadata_confidence * 100)}%` : "—"}
                  </td>
                  <td style={{ padding: "10px 14px", color: "#6c757d", fontSize: 12 }}>
                    {new Date(imp.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
              {imports.length === 0 && (
                <tr><td colSpan={7} style={{ padding: 32, textAlign: "center", color: "#6c757d" }}>No imports yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 12px",
  border: "1px solid #dee2e6",
  borderRadius: 6,
  fontSize: 14,
  boxSizing: "border-box",
};
