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
  /** kWh used that month (5.4); null before SirisOS started counting. */
  energy_kwh?: number | null;
}

export interface Trends {
  today: string;
  months: TrendMonth[];
  cpd: { window_total: number; required: number };
  journal: { current: number; longest: number };
  since: { health: string | null; log: string | null };
  available: { health: boolean; energy?: boolean };
}

export const trends = { get: () => api<Trends>("/api/v1/trends") };
