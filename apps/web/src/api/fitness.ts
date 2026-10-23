import { api } from "./client";

export interface FitnessWeek {
  available: boolean;
  guest_mode: boolean;
  goal_km: number | null;
  km?: number;
  runs?: number;
  exercise_minutes?: number;
  steps_avg?: number | null;
  days?: { date: string; km: number; exercise: number; future: boolean }[];
}

export interface Upkeep {
  sirisos: { version: string };
  sirisai: {
    backups: { newest: string | null; count: number; stale: boolean } | null;
    update: { current: string; latest: string | null; available: boolean };
  } | null;
  certificates: { host: string; expires: string | null; days_left: number | null; warning?: boolean; error?: string }[];
}

export const fitness = {
  week: () => api<FitnessWeek>("/api/v1/fitness"),
  setGoal: (km: number | null) => api<{ goal_km: number | null }>("/api/v1/fitness/goal", { method: "PUT", body: JSON.stringify({ weekly_km: km }) }),
  upkeep: () => api<Upkeep>("/api/v1/hub/upkeep"),
};
