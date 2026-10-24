import { api, json } from "./client";

export type GoalKind = "running_km" | "cpd_hours" | "journal_days" | "tasks_done" | "chartered_ready" | "count" | "done";

export interface YearGoal {
  id: string;
  title: string;
  kind: GoalKind;
  target: number | null;
  unit: string;
  progress: number;
  done: boolean;
  notes: string;
  /** Where it stands now: measured for the first four kinds, your count, or 1/0 for done. */
  value: number | null;
  percent: number | null;
  state: "done" | "on_track" | "behind" | "open" | "unknown";
  source: string | null;
}

export interface YearGoals {
  year: number;
  today: string;
  through_year: number;
  goals: YearGoal[];
  /** January, and no goals yet for this year. */
  set_them: boolean;
}

export const KIND_LABEL: Record<GoalKind, string> = {
  running_km: "Running (km, counted for you)",
  cpd_hours: "CPD hours (counted for you)",
  journal_days: "Journal days (counted for you)",
  tasks_done: "Tasks done (counted for you)",
  chartered_ready: "Chartered application ready (%, from Career)",
  count: "A number I'll count",
  done: "Done or not",
};

const G = "/api/v1/goals";

export const goals = {
  get: (year: number) => api<YearGoals>(`${G}?year=${year}`),
  add: (year: number, goal: { title: string; kind: GoalKind; target?: number | null; unit?: string }) => api<YearGoal>(`${G}?year=${year}`, json(goal)),
  change: (year: number, id: string, changes: Partial<Pick<YearGoal, "title" | "target" | "progress" | "done" | "notes" | "unit">>) =>
    api<YearGoal>(`${G}/${encodeURIComponent(id)}?year=${year}`, { ...json(changes), method: "PATCH" }),
  remove: (year: number, id: string) => api<void>(`${G}/${encodeURIComponent(id)}?year=${year}`, { method: "DELETE" }),
};
