import type { ImportStatus } from "../lib/api";

export type StampTone = "moss" | "clay" | "brass" | "slate";

interface StatusStampProps {
  tone: StampTone;
  label: string;
  title?: string;
}

export function StatusStamp({ tone, label, title }: StatusStampProps) {
  return (
    <span className={`status-stamp status-stamp--${tone}`} title={title}>
      {label}
    </span>
  );
}

const IMPORT_STATUS_STAMP: Record<ImportStatus, { label: string; tone: StampTone }> = {
  pending: { label: "Pending", tone: "slate" },
  importing: { label: "Importing", tone: "brass" },
  imported: { label: "Imported", tone: "moss" },
  needs_review: { label: "Needs Review", tone: "clay" },
  failed: { label: "Failed", tone: "clay" },
};

export function importStatusStamp(status: ImportStatus) {
  return IMPORT_STATUS_STAMP[status];
}
