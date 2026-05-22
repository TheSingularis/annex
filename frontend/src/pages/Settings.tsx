import { useEffect, useState } from "react";

interface Config {
  audiobook_watch_path: string;
  ebook_watch_path: string;
  abs_host: string;
  audiobook_library_path: string;
  ebook_library_path: string;
  confidence_threshold: number;
  poll_interval_seconds: number;
}

interface AbsStatus {
  reachable: boolean;
  authenticated: boolean;
  error: string | null;
}

function AbsStatusBadge({ status, loading }: { status: AbsStatus | null; loading: boolean }) {
  if (loading) {
    return <span style={{ fontSize: 12, color: "#6c757d" }}>Checking...</span>;
  }
  if (!status) return null;

  const { reachable, authenticated, error } = status;
  const ok = reachable && authenticated;
  const color = ok ? "#198754" : reachable ? "#fd7e14" : "#dc3545";
  const label = ok ? "Connected" : reachable ? "Auth failed" : "Unreachable";

  return (
    <span title={error ?? undefined} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, color }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />
      {label}
      {error && !ok && (
        <span style={{ color: "#6c757d", fontStyle: "italic" }}>— {error}</span>
      )}
    </span>
  );
}

export default function Settings() {
  const [config, setConfig] = useState<Config | null>(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [absStatus, setAbsStatus] = useState<AbsStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);

  useEffect(() => {
    fetch("/api/config/")
      .then(r => r.json())
      .then(setConfig)
      .finally(() => setConfigLoading(false));

    checkAbsStatus();
  }, []);

  const checkAbsStatus = () => {
    setStatusLoading(true);
    fetch("/api/config/status")
      .then(r => r.json())
      .then(d => setAbsStatus(d.abs))
      .finally(() => setStatusLoading(false));
  };

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 24 }}>Settings</h1>

      {configLoading ? <div>Loading...</div> : !config ? (
        <div style={{ color: "#dc3545" }}>Failed to load config</div>
      ) : (
        <div style={{ display: "grid", gap: 16, maxWidth: 600 }}>
          <ConfigCard title="Watch Directories">
            <Row label="Audiobooks" value={config.audiobook_watch_path || "—"} />
            <Row label="Ebooks" value={config.ebook_watch_path || "—"} />
          </ConfigCard>

          <ConfigCard title="Library Destinations">
            <Row label="Audiobooks" value={config.audiobook_library_path} />
            <Row label="Ebooks" value={config.ebook_library_path} />
          </ConfigCard>

          <ConfigCard
            title="Audiobookshelf"
            action={
              <button onClick={checkAbsStatus} style={testBtnStyle}>
                Test
              </button>
            }
          >
            <Row label="Host" value={config.abs_host || "—"} />
            <div style={{ paddingTop: 8 }}>
              <AbsStatusBadge status={absStatus} loading={statusLoading} />
            </div>
          </ConfigCard>

          <ConfigCard title="Import Settings">
            <Row label="Confidence threshold" value={`${Math.round(config.confidence_threshold * 100)}%`} />
            <Row label="Scan interval" value={`${config.poll_interval_seconds}s`} />
          </ConfigCard>

          <div style={{ fontSize: 13, color: "#6c757d", background: "#fff3cd", borderRadius: 6, padding: "10px 14px" }}>
            Configuration is managed via <code>appdata/annex/.env</code>. Restart the container after making changes.
          </div>
        </div>
      )}
    </div>
  );
}

function ConfigCard({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,.1)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: "#495057", textTransform: "uppercase", letterSpacing: "0.05em" }}>{title}</div>
        {action}
      </div>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid #f1f3f5", fontSize: 14 }}>
      <span style={{ color: "#6c757d" }}>{label}</span>
      <span style={{ fontFamily: "monospace", fontSize: 13 }}>{value}</span>
    </div>
  );
}

const testBtnStyle: React.CSSProperties = {
  background: "none",
  border: "1px solid #dee2e6",
  borderRadius: 5,
  padding: "3px 10px",
  fontSize: 12,
  cursor: "pointer",
  color: "#495057",
};
