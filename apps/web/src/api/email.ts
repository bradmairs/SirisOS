import { api, json } from "./client";

export interface DraftReply {
  id: string;
  who: string | null;
  subject: string;
  snippet: string;
  draft: string;
  in_drafts_folder: boolean;
  can_send: boolean;
  created_at: string | null;
}

export const email = {
  triage: () => api<{ replies: DraftReply[]; snoozed: number; unavailable: boolean }>("/api/v1/email/triage"),
  send: (id: string, body: string) => api(`/api/v1/attention/${encodeURIComponent(id)}/act`, json({ action: "send", body })),
  snooze: (id: string, until: "later" | "tonight" | "tomorrow") => api<{ id: string; until: string }>(`/api/v1/attention/${encodeURIComponent(id)}/snooze`, json({ until })),
  leave: (id: string) => api(`/api/v1/attention/${encodeURIComponent(id)}/dismiss`, { method: "POST" }),
};
