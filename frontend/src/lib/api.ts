export type ImportStatus = "pending" | "importing" | "imported" | "needs_review" | "failed";
export type Category = "audiobook" | "ebook";

export interface Import {
  id: number;
  hash: string | null;
  name: string;
  category: Category;
  content_path: string;
  status: ImportStatus;
  metadata_confidence: number | null;
  resolved_author: string | null;
  resolved_title: string | null;
  resolved_series: string | null;
  resolved_series_seq: string | null;
  target_path: string | null;
  candidates_json: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface Candidate {
  title: string;
  author: string;
  series: string;
  series_seq: string;
  score: number;
  source: string;
}

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || res.statusText);
  }
  return res.json();
}

export const api = {
  listImports: (status?: ImportStatus) =>
    request<Import[]>(`/imports/${status ? `?status=${status}` : ""}`),

  getImport: (id: number) => request<Import>(`/imports/${id}`),

  manualImport: (body: {
    path: string;
    category: Category;
    author?: string;
    title?: string;
  }) => request<Import>("/imports/manual", { method: "POST", body: JSON.stringify(body) }),

  approveImport: (
    id: number,
    body: { author: string; title: string; series?: string; series_seq?: string; candidate_index?: number }
  ) => request<Import>(`/imports/${id}/approve`, { method: "POST", body: JSON.stringify(body) }),

  retryImport: (id: number) =>
    request<Import>(`/imports/${id}/retry`, { method: "POST" }),

  triggerScan: () =>
    request<{ status: string }>("/imports/scan", { method: "POST" }),

  clearImports: (statuses?: ImportStatus[]) =>
    request<{ deleted: number }>("/imports/clear", {
      method: "POST",
      body: JSON.stringify(statuses ? { statuses } : {}),
    }),

  getSettings: () => request<AllSettings>("/settings/"),
  updateSettings: (body: Partial<AllSettings>) =>
    request<AllSettings>("/settings/", { method: "PUT", body: JSON.stringify(body) }),
  getAbsStatus: () => request<{ abs: AbsStatus }>("/settings/status"),
};

export interface AbsSettings {
  abs_host: string;
  abs_api_key: string;
  abs_audiobook_library_id: string;
  abs_ebook_library_id: string;
}

export interface PathSettings {
  audiobook_watch_path: string;
  ebook_watch_path: string;
  audiobook_library_path: string;
  ebook_library_path: string;
}

export type AllSettings = AbsSettings & PathSettings;

export interface AbsStatus {
  reachable: boolean;
  authenticated: boolean;
  error: string | null;
}
