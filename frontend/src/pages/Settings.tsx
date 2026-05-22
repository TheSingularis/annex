import { useEffect, useState } from "react";

interface Config {
  qbit_host: string;
  qbit_port: number;
  abs_host: string;
  audiobook_library_path: string;
  ebook_library_path: string;
  confidence_threshold: number;
  poll_interval_seconds: number;
}

export default function Settings() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/config/")
      .then(r => r.json())
      .then(setConfig)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 24 }}>Settings</h1>

      {loading ? <div>Loading...</div> : !config ? <div style={{ color: "#dc3545" }}>Failed to load config</div> : (
        <div style={{ display: "grid", gap: 16, maxWidth: 600 }}>
          <ConfigCard title="qBittorrent">
            <Row label="Host" value={`${config.qbit_host}:${config.qbit_port}`} />
          </ConfigCard>
          <ConfigCard title="Audiobookshelf">
            <Row label="Host" value={config.abs_host} />
          </ConfigCard>
          <ConfigCard title="Libraries">
            <Row label="Audiobooks" value={config.audiobook_library_path} />
            <Row label="Ebooks" value={config.ebook_library_path} />
          </ConfigCard>
          <ConfigCard title="Import Settings">
            <Row label="Confidence threshold" value={`${Math.round(config.confidence_threshold * 100)}%`} />
            <Row label="Poll interval" value={`${config.poll_interval_seconds}s`} />
          </ConfigCard>
          <div style={{ fontSize: 13, color: "#6c757d", background: "#fff3cd", borderRadius: 6, padding: "10px 14px" }}>
            Configuration is managed via environment variables in <code>.env</code>. Restart the container after making changes.
          </div>
        </div>
      )}
    </div>
  );
}

function ConfigCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: 20, boxShadow: "0 1px 3px rgba(0,0,0,.1)" }}>
      <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 13, color: "#495057", textTransform: "uppercase", letterSpacing: "0.05em" }}>{title}</div>
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
