import { useEffect, useState } from "react";
import { api, AbsSettings, PathSettings, AllSettings, ImportStatus } from "../lib/api";
import { useTheme } from "../lib/ThemeContext";

interface EnvConfig {
  confidence_threshold: number;
  poll_interval_seconds: number;
}

function StatusDot({ status, loading }: { status: AbsStatus | null; loading: boolean }) {
  if (loading) return <span style={{ fontSize: 12, color: "#6c757d" }}>Checking...</span>;
  if (!status) return null;
  const ok = status.reachable && status.authenticated;
  const color = ok ? "#198754" : status.reachable ? "#fd7e14" : "#dc3545";
  const label = ok ? "Connected" : status.reachable ? "Auth failed" : "Unreachable";
  return (
    <span title={status.error ?? undefined} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, color }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />
      {label}
      {!ok && status.error && <span style={{ color: "#6c757d", fontStyle: "italic" }}>— {status.error}</span>}
    </span>
  );
}

interface AbsStatus {
  reachable: boolean;
  authenticated: boolean;
  error: string | null;
}

export default function Settings() {
  const { tokens } = useTheme();
  const [absForm, setAbsForm] = useState<AbsSettings>({ abs_host: "", abs_api_key: "", abs_audiobook_library_id: "", abs_ebook_library_id: "" });
  const [pathForm, setPathForm] = useState<PathSettings>({ audiobook_watch_path: "", ebook_watch_path: "", audiobook_library_path: "", ebook_library_path: "" });
  const [envConfig, setEnvConfig] = useState<EnvConfig | null>(null);
  const [absStatus, setAbsStatus] = useState<AbsStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [absSaving, setAbsSaving] = useState(false);
  const [absSaved, setAbsSaved] = useState(false);
  const [pathSaving, setPathSaving] = useState(false);
  const [pathSaved, setPathSaved] = useState(false);
  const [clearing, setClearing] = useState<string | null>(null);
  const [clearMsg, setClearMsg] = useState("");

  useEffect(() => {
    api.getSettings().then((d: AllSettings) => {
      setAbsForm({ abs_host: d.abs_host, abs_api_key: d.abs_api_key, abs_audiobook_library_id: d.abs_audiobook_library_id, abs_ebook_library_id: d.abs_ebook_library_id });
      setPathForm({ audiobook_watch_path: d.audiobook_watch_path, ebook_watch_path: d.ebook_watch_path, audiobook_library_path: d.audiobook_library_path, ebook_library_path: d.ebook_library_path });
      if (d.abs_host) {
        setStatusLoading(true);
        api.getAbsStatus().then(r => setAbsStatus(r.abs)).finally(() => setStatusLoading(false));
      }
    });
    fetch("/api/config/").then(r => r.json()).then(setEnvConfig);
  }, []);

  const checkStatus = () => {
    if (!absForm.abs_host) {
      setAbsStatus({ reachable: false, authenticated: false, error: "Host URL is required" });
      return;
    }
    setStatusLoading(true);
    setAbsStatus(null);
    api.getAbsStatus().then(d => setAbsStatus(d.abs)).finally(() => setStatusLoading(false));
  };

  const handleAbsSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setAbsSaving(true);
    setAbsSaved(false);
    try {
      const updated = await api.updateSettings(absForm);
      setAbsForm({ abs_host: updated.abs_host, abs_api_key: updated.abs_api_key, abs_audiobook_library_id: updated.abs_audiobook_library_id, abs_ebook_library_id: updated.abs_ebook_library_id });
      setAbsSaved(true);
      checkStatus();
      setTimeout(() => setAbsSaved(false), 3000);
    } finally {
      setAbsSaving(false);
    }
  };

  const handlePathSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setPathSaving(true);
    setPathSaved(false);
    try {
      const updated = await api.updateSettings(pathForm);
      setPathForm({ audiobook_watch_path: updated.audiobook_watch_path, ebook_watch_path: updated.ebook_watch_path, audiobook_library_path: updated.audiobook_library_path, ebook_library_path: updated.ebook_library_path });
      setPathSaved(true);
      setTimeout(() => setPathSaved(false), 3000);
    } finally {
      setPathSaving(false);
    }
  };

  const handleClear = async (label: string, statuses?: ImportStatus[]) => {
    if (!confirm(`Clear ${label} import records? This cannot be undone.`)) return;
    setClearing(label);
    setClearMsg("");
    try {
      const { deleted } = await api.clearImports(statuses);
      setClearMsg(`Removed ${deleted} record${deleted !== 1 ? "s" : ""}.`);
      setTimeout(() => setClearMsg(""), 4000);
    } finally {
      setClearing(null);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "8px 12px", border: `1px solid ${tokens.inputBorder}`,
    borderRadius: 6, fontSize: 14, boxSizing: "border-box",
    background: tokens.surface, color: tokens.text,
  };

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 24, color: tokens.text }}>Settings</h1>

      <div style={{ display: "grid", gap: 16, maxWidth: 600 }}>

        {/* Paths — editable */}
        <div style={{ background: tokens.surface, borderRadius: 8, padding: 20, boxShadow: tokens.shadow }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: tokens.textMuted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 16 }}>
            Paths
          </div>
          <form onSubmit={handlePathSave}>
            <div style={{ display: "grid", gap: 10 }}>
              <label style={{ fontSize: 13, color: tokens.textMuted }}>
                Audiobook watch directory
                <input style={{ ...inputStyle, marginTop: 4 }} placeholder="/downloads/audiobooks" value={pathForm.audiobook_watch_path} onChange={e => setPathForm(f => ({ ...f, audiobook_watch_path: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: tokens.textMuted }}>
                Ebook watch directory
                <input style={{ ...inputStyle, marginTop: 4 }} placeholder="/downloads/ebooks" value={pathForm.ebook_watch_path} onChange={e => setPathForm(f => ({ ...f, ebook_watch_path: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: tokens.textMuted }}>
                Audiobook library
                <input style={{ ...inputStyle, marginTop: 4 }} placeholder="/library/audiobooks" value={pathForm.audiobook_library_path} onChange={e => setPathForm(f => ({ ...f, audiobook_library_path: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: tokens.textMuted }}>
                Ebook library
                <input style={{ ...inputStyle, marginTop: 4 }} placeholder="/library/ebooks" value={pathForm.ebook_library_path} onChange={e => setPathForm(f => ({ ...f, ebook_library_path: e.target.value }))} />
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 4 }}>
                <button type="submit" disabled={pathSaving} style={{ background: "#0d6efd", color: "#fff", border: "none", borderRadius: 6, padding: "8px 16px", cursor: "pointer", fontSize: 14 }}>
                  {pathSaving ? "Saving..." : "Save"}
                </button>
                {pathSaved && <span style={{ fontSize: 13, color: "#198754" }}>Saved</span>}
              </div>
            </div>
          </form>
        </div>

        {/* ABS — editable */}
        <div style={{ background: tokens.surface, borderRadius: 8, padding: 20, boxShadow: tokens.shadow }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: tokens.textMuted, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Audiobookshelf
            </div>
            <StatusDot status={absStatus} loading={statusLoading} />
          </div>
          <form onSubmit={handleAbsSave}>
            <div style={{ display: "grid", gap: 10 }}>
              <label style={{ fontSize: 13, color: tokens.textMuted }}>
                Host URL
                <input style={{ ...inputStyle, marginTop: 4 }} placeholder="http://192.168.1.100:13378" value={absForm.abs_host} onChange={e => setAbsForm(f => ({ ...f, abs_host: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: tokens.textMuted }}>
                API Key
                <input style={{ ...inputStyle, marginTop: 4 }} type="password" placeholder="Your ABS API key" value={absForm.abs_api_key} onChange={e => setAbsForm(f => ({ ...f, abs_api_key: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: tokens.textMuted }}>
                Audiobook Library ID
                <input style={{ ...inputStyle, marginTop: 4 }} placeholder="e.g. lib_abc123" value={absForm.abs_audiobook_library_id} onChange={e => setAbsForm(f => ({ ...f, abs_audiobook_library_id: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: tokens.textMuted }}>
                Ebook Library ID
                <input style={{ ...inputStyle, marginTop: 4 }} placeholder="e.g. lib_def456" value={absForm.abs_ebook_library_id} onChange={e => setAbsForm(f => ({ ...f, abs_ebook_library_id: e.target.value }))} />
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 4 }}>
                <button type="submit" disabled={absSaving} style={{ background: "#0d6efd", color: "#fff", border: "none", borderRadius: 6, padding: "8px 16px", cursor: "pointer", fontSize: 14 }}>
                  {absSaving ? "Saving..." : "Save"}
                </button>
                <button type="button" onClick={checkStatus} style={{ background: "none", border: `1px solid ${tokens.border}`, borderRadius: 6, padding: "7px 14px", cursor: "pointer", fontSize: 13, color: tokens.textMuted }}>
                  Test connection
                </button>
                {absSaved && <span style={{ fontSize: 13, color: "#198754" }}>Saved</span>}
              </div>
            </div>
          </form>
        </div>

        {/* Scan settings — read-only from env */}
        {envConfig && (
          <div style={{ background: tokens.surface, borderRadius: 8, padding: 20, boxShadow: tokens.shadow }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: tokens.textMuted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>Import Settings</div>
            <Row label="Confidence threshold" value={`${Math.round(envConfig.confidence_threshold * 100)}%`} tokens={tokens} />
            <Row label="Scan interval" value={`${envConfig.poll_interval_seconds}s`} tokens={tokens} />
          </div>
        )}

        <div style={{ fontSize: 13, color: tokens.warningText, background: tokens.warningBg, borderRadius: 6, padding: "10px 14px" }}>
          Confidence threshold and scan interval are configured via <code>appdata/annex/.env</code>. Restart the container after making changes.
        </div>

        {/* Import record management */}
        <div style={{ background: tokens.surface, borderRadius: 8, padding: 20, boxShadow: tokens.shadow }}>
          <div style={{ fontWeight: 600, fontSize: 13, color: tokens.textMuted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>
            Import Records
          </div>
          <p style={{ fontSize: 13, color: tokens.textMuted, margin: "0 0 14px" }}>
            Clear records from the import history. Files in your library and download folders are not affected.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <button onClick={() => handleClear("failed", ["failed"])} disabled={!!clearing} style={{ background: "none", border: `1px solid ${tokens.border}`, borderRadius: 6, padding: "7px 14px", cursor: "pointer", fontSize: 13, color: tokens.textMuted }}>
              {clearing === "failed" ? "Clearing…" : "Clear failed"}
            </button>
            <button onClick={() => handleClear("needs review", ["needs_review"])} disabled={!!clearing} style={{ background: "none", border: `1px solid ${tokens.border}`, borderRadius: 6, padding: "7px 14px", cursor: "pointer", fontSize: 13, color: tokens.textMuted }}>
              {clearing === "needs review" ? "Clearing…" : "Clear needs review"}
            </button>
            <button onClick={() => handleClear("all")} disabled={!!clearing} style={{ background: "none", border: `1px solid #dc3545`, borderRadius: 6, padding: "7px 14px", cursor: "pointer", fontSize: 13, color: "#dc3545" }}>
              {clearing === "all" ? "Clearing…" : "Clear all"}
            </button>
          </div>
          {clearMsg && <div style={{ marginTop: 10, fontSize: 13, color: "#198754" }}>{clearMsg}</div>}
        </div>

      </div>
    </div>
  );
}

function Row({ label, value, tokens }: { label: string; value: string; tokens: ReturnType<typeof useTheme>["tokens"] }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: `1px solid ${tokens.border}`, fontSize: 14 }}>
      <span style={{ color: tokens.textMuted }}>{label}</span>
      <span style={{ fontFamily: "monospace", fontSize: 13, color: tokens.text }}>{value}</span>
    </div>
  );
}
