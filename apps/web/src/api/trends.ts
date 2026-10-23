import { api } from "./client";

export interface TrendMonth {
  month: string;
  cpd_hours: number;
  running_km: number;
  exercise_minutes: number;
  steps: number | null;
  tasks_done: number;
  inbox: number | null;
  journal_days: number;
  wrapups: number;
  reviews: number;
}

export interface Trends {
  today: string;
  months: TrendMonth[];
  cpd: { window_total: number; required: number };
  journal: { current: number; longest: number };
  since: { health: string | null; log: string | null };
  available: { health: boolean };
}

export const trends = { get: () => api<Trends>("/api/v1/trends") };
