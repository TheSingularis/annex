import { useEffect, useState } from "react";
import { api, AbsSettings, PathSettings, AllSettings, ImportStatus } from "../lib/api";
import { CatalogCard } from "../components/CatalogCard";
import { StatusStamp, StampTone } from "../components/StatusStamp";
import { Button } from "../components/Button";
import { Input } from "../components/Input";

interface EnvConfig {
  confidence_threshold: number;
  poll_interval_seconds: number;
  version: string;
}

interface AbsStatus {
  reachable: boolean;
  authenticated: boolean;
  error: string | null;
}

function AbsConnectionStamp({ status, loading }: { status: AbsStatus | null; loading: boolean }) {
  if (loading) return <StatusStamp tone="slate" label="Checking" />;
  if (!status) return null;
  const ok = status.reachable && status.authenticated;
  const tone: StampTone = ok ? "moss" : status.reachable ? "brass" : "clay";
  const label = ok ? "Connected" : status.reachable ? "Auth failed" : "Unreachable";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <StatusStamp tone={tone} label={label} title={status.error ?? undefined} />
      {!ok && status.error && <span style={{ color: "var(--text-muted)", fontSize: 12, fontStyle: "italic" }}>{status.error}</span>}
    </span>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 15, color: "var(--text)",
      borderBottom: "1px solid var(--brass)", paddingBottom: 8, marginBottom: 16,
    }}>
      {children}
    </div>
  );
}

export default function Settings() {
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

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 24 }}>Settings</h1>

      <div style={{ display: "grid", gap: 16, maxWidth: 600 }}>

        {/* Paths — editable */}
        <CatalogCard tone="brass">
          <SectionHeading>Paths</SectionHeading>
          <form onSubmit={handlePathSave}>
            <div style={{ display: "grid", gap: 10 }}>
              <label style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Audiobook watch directory
                <Input style={{ marginTop: 4 }} placeholder="/downloads/audiobooks" value={pathForm.audiobook_watch_path} onChange={e => setPathForm(f => ({ ...f, audiobook_watch_path: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Ebook watch directory
                <Input style={{ marginTop: 4 }} placeholder="/downloads/ebooks" value={pathForm.ebook_watch_path} onChange={e => setPathForm(f => ({ ...f, ebook_watch_path: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Audiobook library
                <Input style={{ marginTop: 4 }} placeholder="/library/audiobooks" value={pathForm.audiobook_library_path} onChange={e => setPathForm(f => ({ ...f, audiobook_library_path: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Ebook library
                <Input style={{ marginTop: 4 }} placeholder="/library/ebooks" value={pathForm.ebook_library_path} onChange={e => setPathForm(f => ({ ...f, ebook_library_path: e.target.value }))} />
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 4 }}>
                <Button type="submit" variant="primary" disabled={pathSaving}>
                  {pathSaving ? "Saving..." : "Save"}
                </Button>
                {pathSaved && <StatusStamp tone="moss" label="Saved" />}
              </div>
            </div>
          </form>
        </CatalogCard>

        {/* ABS — editable */}
        <CatalogCard tone="brass">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 16 }}>
            <SectionHeading>Audiobookshelf</SectionHeading>
            <AbsConnectionStamp status={absStatus} loading={statusLoading} />
          </div>
          <form onSubmit={handleAbsSave}>
            <div style={{ display: "grid", gap: 10 }}>
              <label style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Host URL
                <Input style={{ marginTop: 4 }} placeholder="http://192.168.1.100:13378" value={absForm.abs_host} onChange={e => setAbsForm(f => ({ ...f, abs_host: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: "var(--text-muted)" }}>
                API Key
                <Input style={{ marginTop: 4 }} type="password" placeholder="Your ABS API key" value={absForm.abs_api_key} onChange={e => setAbsForm(f => ({ ...f, abs_api_key: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Audiobook Library ID
                <Input style={{ marginTop: 4 }} placeholder="e.g. lib_abc123" value={absForm.abs_audiobook_library_id} onChange={e => setAbsForm(f => ({ ...f, abs_audiobook_library_id: e.target.value }))} />
              </label>
              <label style={{ fontSize: 13, color: "var(--text-muted)" }}>
                Ebook Library ID
                <Input style={{ marginTop: 4 }} placeholder="e.g. lib_def456" value={absForm.abs_ebook_library_id} onChange={e => setAbsForm(f => ({ ...f, abs_ebook_library_id: e.target.value }))} />
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 4 }}>
                <Button type="submit" variant="primary" disabled={absSaving}>
                  {absSaving ? "Saving..." : "Save"}
                </Button>
                <Button type="button" onClick={checkStatus}>Test connection</Button>
                {absSaved && <StatusStamp tone="moss" label="Saved" />}
              </div>
            </div>
          </form>
        </CatalogCard>

        {/* Scan settings — read-only from env */}
        {envConfig && (
          <CatalogCard tone="slate">
            <SectionHeading>Import Settings</SectionHeading>
            <Row label="Confidence threshold" value={`${Math.round(envConfig.confidence_threshold * 100)}%`} />
            <Row label="Scan interval" value={`${envConfig.poll_interval_seconds}s`} />
          </CatalogCard>
        )}

        <div style={{ fontSize: 13, color: "var(--warning-text)", background: "var(--warning-bg)", borderRadius: "var(--radius-card)", padding: "10px 14px" }}>
          Confidence threshold and scan interval are configured via <code>appdata/annex/.env</code>. Restart the container after making changes.
        </div>

        {/* Import record management */}
        <CatalogCard tone="clay">
          <SectionHeading>Import Records</SectionHeading>
          <p style={{ fontSize: 13, color: "var(--text-muted)", margin: "0 0 14px" }}>
            Clear records from the import history. Files in your library and download folders are not affected.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <Button onClick={() => handleClear("failed", ["failed"])} disabled={!!clearing}>
              {clearing === "failed" ? "Clearing…" : "Clear failed"}
            </Button>
            <Button onClick={() => handleClear("needs review", ["needs_review"])} disabled={!!clearing}>
              {clearing === "needs review" ? "Clearing…" : "Clear needs review"}
            </Button>
            <Button variant="danger" onClick={() => handleClear("all")} disabled={!!clearing}>
              {clearing === "all" ? "Clearing…" : "Clear all"}
            </Button>
          </div>
          {clearMsg && <div style={{ marginTop: 10, fontSize: 13, color: "var(--moss)" }}>{clearMsg}</div>}
        </CatalogCard>

        {envConfig && (
          <div style={{ textAlign: "center", fontSize: 12, color: "var(--text-muted)", padding: "4px 0" }}>
            Annex <span className="mono">{envConfig.version}</span>
          </div>
        )}

      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)", fontSize: 14 }}>
      <span style={{ color: "var(--text-muted)" }}>{label}</span>
      <span className="mono" style={{ fontSize: 13, color: "var(--text)" }}>{value}</span>
    </div>
  );
}
