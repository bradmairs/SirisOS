import { api } from "./client";
import type { TaskItem } from "./tasks";

/** The working day (7.2): GET /api/v1/work. */
export interface WorkDay {
  date: string;
  local_time: string;
  hours: { start: string; end: string; on: boolean; workday: boolean; minutes_left: number | null; minutes_in: number | null };
  tasks: { groups: Partial<Record<"overdue" | "today" | "week", TaskItem[]>>; counts: Partial<Record<"overdue" | "today" | "week", number>> };
  todos: { task: string; note: string; due: string | null }[] | null;
  engineering: { current: { id: string; name: string; kind: string; tags: string[] } | null; active: { id: string; name: string; kind: string; tags: string[] }[] };
  cpd: { total: number; required: number; short: number; window?: { from: string; to: string };
    minimums?: { category: string; label: string; hours: number; minimum: number; short: number }[] } | null;
  week?: { days: { date: string; weekday: string; done: number; focus_min: number }[]; done_today: number; focus_today: number };
  apps?: { id: string; name: string; url: string; icon: string | null; note: string }[];
  notes?: { title: string; path: string; type: string; as_of: string; tags: string[]; excerpt: string }[] | null;
  /** The end-of-work wrap-up (7.5): due from 15 minutes before home time, unless done. */
  wrapup?: { due: boolean; saved: WorkWrapUpSaved | null; next_workday: string };
  /** How close the chartered application is, and how it's moved (7.5). */
  chartership?: Chartership | null;
}

export interface WorkWrapUpSaved { done: string; carried: number; first: string | null; note: string; cpd: unknown; saved_as: string | null; next_workday: string; at: string }

export interface ChartershipPoint { percent: number; solid: number; elements: number; evidence: number }
export interface Chartership {
  now: ChartershipPoint;
  trend: (ChartershipPoint & { week: string })[];
  change: { percent: number; solid: number; since: string };
  next: string | null;
  weakest: { id: string; title: string; strength: "none" | "thin" | "solid" }[];
}

export type CpdCategory = "area" | "risk" | "business" | "other";

export const work = {
  get: () => api<WorkDay>("/api/v1/work"),
  focus: (minutes: number) => api<{ today: number }>("/api/v1/work/focus", { method: "POST", body: JSON.stringify({ minutes }) }),
  todoDone: () => api<{ ok: boolean }>("/api/v1/work/todo-done", { method: "POST" }),
  logCpd: (c: { title: string; hours: number; category: CpdCategory; date?: string; provider?: string }) =>
    api<{ record: unknown; cpd: WorkDay["cpd"] }>("/api/v1/work/cpd", { method: "POST", body: JSON.stringify(c) }),
  wrapUp: (w: { done: string; carry: string[]; first: string; note: string; cpd?: { title: string; hours: number; category: CpdCategory } | null }) =>
    api<WorkWrapUpSaved>("/api/v1/work/wrapup", { method: "POST", body: JSON.stringify(w) }),
};

/** How far through the working day `at` is, 0 to 1 (0 before it starts, 1 after it ends). */
export function dayFraction(start: string, end: string, at = new Date()): number {
  const m = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
  const now = at.getHours() * 60 + at.getMinutes() + at.getSeconds() / 60;
  return Math.min(1, Math.max(0, (now - m(start)) / Math.max(1, m(end) - m(start))));
}

/** "3 h 20 min", "45 min". */
export function span(minutes: number): string {
  const m = Math.max(0, Math.round(minutes));
  const h = Math.floor(m / 60);
  return h ? `${h} h${m % 60 ? ` ${m % 60} min` : ""}` : `${m} min`;
}
