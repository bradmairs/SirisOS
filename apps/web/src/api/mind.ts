import { api, json } from "./client";

/** Mental health (9.1): mood (Apple Health's State of Mind, or the 1-5 quick log) on one -1..1 scale, mindful minutes,
 * the calming tools and the journal. Clarity is fetched on its own, only when its card is opened. */
export interface MindDay { date: string; valence: number | null; word: string | null; entries?: number | null; logged?: number | null;
  mindful_minutes: number | null; here_minutes: number | null; sleep_hours?: number | null; exercise_minutes?: number | null }
export interface JournalEntry { id: string; at: string; kind: "gratitude" | "reframe" | "note"; text: string; [k: string]: string }
export interface Mind {
  available: boolean; days: MindDay[]; today: MindDay | null;
  week: { valence: number | null; word: string | null; before: number | null; mindful_minutes: number; mindful_before: number; mood_days: number };
  patterns: { key: string; text: string; with: number; without: number; days: number }[];
  journal: JournalEntry[]; tools_minutes_week: number;
}
export interface Clarity {
  started: string | null; streak: number; best: number; next: { days: number; left: number } | null; clear_last_30: number;
  month: { date: string; status: "clear" | "slip" | null }[]; checked_today: "clear" | "slip" | null;
  urges_week: number; rode_out_week: number; rode_out_all: number; triggers: { trigger: string; count: number }[];
  times: { part: string; count: number }[]; urges: { id: string; at: string; trigger: string; outcome: string; note: string }[];
  reasons: string[]; plan: string[];
}

const M = "/api/v1/mind";
export const mind = {
  get: () => api<Mind>(M),
  journal: (kind: JournalEntry["kind"], text: string, extra: Record<string, string> = {}) => api<JournalEntry>(`${M}/journal`, json({ kind, text, extra })),
  unjournal: (id: string) => api<{ deleted: string }>(`${M}/journal/${encodeURIComponent(id)}`, { method: "DELETE" }),
  session: (tool: "breathing" | "grounding" | "urge", seconds: number) => api<unknown>(`${M}/sessions`, json({ tool, seconds })),
  clarity: () => api<Clarity>(`${M}/clarity`),
  start: (date?: string) => api<Clarity>(`${M}/clarity/start`, json({ date: date ?? null })),
  check: (status: "clear" | "slip", note = "") => api<Clarity>(`${M}/clarity/check`, json({ status, note })),
  urge: (trigger: string, outcome: "rode" | "slip", note = "") => api<Clarity>(`${M}/clarity/urge`, json({ trigger, outcome, note })),
  plan: (reasons: string[], plan: string[]) => api<Clarity>(`${M}/clarity/plan`, { method: "PUT", body: JSON.stringify({ reasons, plan }) }),
};
