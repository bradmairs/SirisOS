import { api, json } from "./client";

export interface Race { name: string; date: string; distance_km: number; goal_time?: string; start_km?: number | null }
export interface Session { date: string; kind: "easy" | "quality" | "long" | "race"; km: number; title: string; changed?: boolean }
export interface PlanWeek { week_of: string; km: number; kind: "build" | "easier" | "taper" | "race"; done_km: number | null; sessions: Session[] }

export interface Training {
  today: string;
  health: boolean;
  recovery: { level: "good" | "easy" | "rest"; notes: string[]; known: boolean };
  plan: { race: Race; start_km: number; days_to_go: number; weeks: PlanWeek[] } | null;
  this_week: PlanWeek | null;
  session: Session | null;
  recent_weekly_km: number;
}

export interface HealthImportStatus {
  has_key: boolean;
  key_hint: string | null;
  made: string | null;
  path: string;
  last: { at: string; days?: string[]; format?: string; error?: string } | null;
  last_ok: { at: string; days?: string[]; format?: string } | null;
}

export const training = {
  get: () => api<Training>("/api/v1/training"),
  setRace: (race: Race) => api<Training>("/api/v1/training/race", { ...json(race), method: "PUT" }),
  clearRace: () => api<Training>("/api/v1/training/race", { method: "DELETE" }),
  feed: () => api<{ path: string }>("/api/v1/training/feed"),
  newFeed: () => api<{ path: string }>("/api/v1/training/feed/new", { method: "POST" }),
  importStatus: () => api<HealthImportStatus>("/api/v1/health/import/status"),
  newKey: () => api<{ key: string; path: string }>("/api/v1/health/import/key", { method: "POST" }),
};

export const DISTANCES: [number, string][] = [[5, "5 km"], [10, "10 km"], [21.1, "Half marathon"], [42.2, "Marathon"]];
