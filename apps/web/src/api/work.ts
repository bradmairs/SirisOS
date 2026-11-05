import { api } from "./client";
import type { TaskItem } from "./tasks";

/** The working day (7.2): GET /api/v1/work. */
export interface WorkEvent { title: string; start: string; end?: string | null; all_day: boolean; location: string | null }
export interface WorkDay {
  date: string;
  local_time: string;
  hours: { start: string; end: string; on: boolean; workday: boolean; minutes_left: number | null; minutes_in: number | null };
  events: WorkEvent[] | null;
  next: (WorkEvent & { in_minutes: number; now: boolean }) | null;
  tasks: { groups: Partial<Record<"overdue" | "today" | "week", TaskItem[]>>; counts: Partial<Record<"overdue" | "today" | "week", number>> };
  projects: { title: string; path?: string | null; status?: string | null; due: string | null; days_left: number | null; open_tasks: number }[] | null;
  todos: { task: string; note: string; due: string | null }[] | null;
  engineering: { current: { id: string; name: string; kind: string; tags: string[] } | null; active: { id: string; name: string; kind: string; tags: string[] }[] };
  cpd: { total: number; required: number; short: number } | null;
}

export const work = {
  get: () => api<WorkDay>("/api/v1/work"),
};

/** "3 h 20 min", "45 min". */
export function span(minutes: number): string {
  const m = Math.max(0, Math.round(minutes));
  const h = Math.floor(m / 60);
  return h ? `${h} h${m % 60 ? ` ${m % 60} min` : ""}` : `${m} min`;
}
