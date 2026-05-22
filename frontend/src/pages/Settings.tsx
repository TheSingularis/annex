import { useEffect, useState } from "react";
import { api, AbsSettings, AbsStatus } from "../lib/api";
import { useTheme } from "../lib/ThemeContext";

interface Config {
  audiobook_watch_path: string;
  ebook_watch_path: string;
  audiobook_library_path: string;
  ebook_library_path: string;
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

export default function Settings() {
  const { tokens } = useTheme();
  const [config, setConfig] = useState<Config | null>(null);
  const [absForm, setAbsForm] = useState<AbsSettings>({ abs_host: "", abs_api_key: "", abs_audiobook_library_id: "", abs_ebook_library_id: "" });
  const [absStatus, setAbsStatus] = useState<AbsStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch("/api/config/").then(r => r.json()).then(setConfig);
    api.getSettings().then(setAbsForm);
    checkStatus();
  }, []);

  const checkStatus = () => {
    setStatusLoading(true);
    api.getAbsStatus().then(d => setAbsStatus(d.abs)).finally(() => setStatusLoading(false));
  };

  const handleAbsSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    try {
      const updated = await api.updateSettings(absForm);
      setAbsForm(updated);
      setSaved(true);
      checkStatus();
      setTimeout(() => setSaved(false), 3000);
    } finally {
      setSaving(false);
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

        {/* ABS — editable form */}
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
                <input
                  style={{ ...inputStyle, marginTop: 4 }}
                  placeholder="http://192.168.1.100:13378"
                  value={absForm.abs_host}
                  onChange={e => setAbsForm(f => ({ ...f, abs_host: e.target.value }))}
                />
              </label>
              <label style={{ fontSize: 13, color: tokens.textMuted }}>
                API Key
                <input
                  style={{ ...inputStyle, marginTop: 4 }}
                  type="password"
                  placeholder="Your ABS API key"
                  value={absForm.abs_api_key}
                  onChange={e => setAbsForm(f => ({ ...f, abs_api_key: e.target.value }))}
                />
              </label>
              <label style={{ fontSize: 13, color: tokens.textMuted }}>
                Audiobook Library ID
                <input
                  style={{ ...inputStyle, marginTop: 4 }}
                  placeholder="e.g. lib_abc123"
                  value={absForm.abs_audiobook_library_id}
                  onChange={e => setAbsForm(f => ({ ...f, abs_audiobook_library_id: e.target.value }))}
                />
              </label>
              <label style={{ fontSize: 13, color: tokens.textMuted }}>
                Ebook Library ID
                <input
                  style={{ ...inputStyle, marginTop: 4 }}
                  placeholder="e.g. lib_def456"
                  value={absForm.abs_ebook_library_id}
                  onChange={e => setAbsForm(f => ({ ...f, abs_ebook_library_id: e.target.value }))}
                />
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 4 }}>
                <button
                  type="submit"
                  disabled={saving}
                  style={{ background: "#0d6efd", color: "#fff", border: "none", borderRadius: 6, padding: "8px 16px", cursor: "pointer", fontSize: 14 }}
                >
                  {saving ? "Saving..." : "Save"}
                </button>
                <button
                  type="button"
                  onClick={checkStatus}
                  style={{ background: "none", border: `1px solid ${tokens.border}`, borderRadius: 6, padding: "7px 14px", cursor: "pointer", fontSize: 13, color: tokens.textMuted }}
                >
                  Test connection
                </button>
                {saved && <span style={{ fontSize: 13, color: "#198754" }}>Saved</span>}
              </div>
            </div>
          </form>
        </div>

        {/* Container config — read-only */}
        {config && (
          <>
            <ConfigCard title="Watch Directories" tokens={tokens}>
              <Row label="Audiobooks" value={config.audiobook_watch_path || "—"} tokens={tokens} />
              <Row label="Ebooks" value={config.ebook_watch_path || "—"} tokens={tokens} />
            </ConfigCard>
            <ConfigCard title="Library Destinations" tokens={tokens}>
              <Row label="Audiobooks" value={config.audiobook_library_path} tokens={tokens} />
              <Row label="Ebooks" value={config.ebook_library_path} tokens={tokens} />
            </ConfigCard>
            <ConfigCard title="Import Settings" tokens={tokens}>
              <Row label="Confidence threshold" value={`${Math.round(config.confidence_threshold * 100)}%`} tokens={tokens} />
              <Row label="Scan interval" value={`${config.poll_interval_seconds}s`} tokens={tokens} />
            </ConfigCard>
          </>
        )}

        <div style={{ fontSize: 13, color: tokens.warningText, background: tokens.warningBg, borderRadius: 6, padding: "10px 14px" }}>
          Watch paths, library paths, and scan settings are configured via <code>appdata/annex/.env</code>. Restart the container after making changes.
        </div>
      </div>
    </div>
  );
}

function ConfigCard({ title, children, tokens }: { title: string; children: React.ReactNode; tokens: ReturnType<typeof useTheme>["tokens"] }) {
  return (
    <div style={{ background: tokens.surface, borderRadius: 8, padding: 20, boxShadow: tokens.shadow }}>
      <div style={{ fontWeight: 600, fontSize: 13, color: tokens.textMuted, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 12 }}>{title}</div>
      {children}
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
