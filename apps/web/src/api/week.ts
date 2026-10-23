import { api } from "./client";
import type { CpdCategory } from "./career";

export interface WeekEvent {
  title: string;
  start: string | null;
  end: string | null;
  all_day: boolean;
  location: string | null;
  calendar: string | null;
  cpd?: { hours: number; category: CpdCategory };
}

export interface WeekDay {
  date: string;
  events: WeekEvent[];
  forecast: { conditions: string | null; high_c: number | null; low_c: number | null; rain_chance_percent: number | null } | null;
  due: { title: string; kind: "project" | "goal"; source: string }[];
  cpd_hours: number;
}

export interface Week {
  start: string;
  end: string;
  today: string;
  days: WeekDay[];
  overdue: { title: string; detail: string; source: string }[];
  /** What matters this week, from last Sunday's review (3.5). */
  focus?: { week_of: string; text: string } | null;
  cpd: { logged: number; planned: number };
  guest_mode: boolean;
  unavailable: string[];
}

export const week = {
  get: (start?: string) => api<Week>(`/api/v1/week${start ? `?start=${start}` : ""}`),
};

/** YYYY-MM-DD of `iso` moved by `days`, in local dates. */
export function shift(iso: string, days: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const out = new Date(y, m - 1, d + days);
  return `${out.getFullYear()}-${String(out.getMonth() + 1).padStart(2, "0")}-${String(out.getDate()).padStart(2, "0")}`;
}
