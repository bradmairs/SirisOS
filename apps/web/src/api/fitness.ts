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
    update: {
      current: string; latest: string | null; available: boolean;
      /** 6.4 (SirisAI 4.03): whether the server's updater checks in, what's waiting, how the last one went. */
      mode?: string | null; updater_running?: boolean | null; waiting?: string | null;
      last?: { state?: string; detail?: string; version?: string; at?: string } | null;
    };
  } | null;
  certificates: { host: string; expires: string | null; days_left: number | null; warning?: boolean; error?: string }[];
}

export const fitness = {
  week: () => api<FitnessWeek>("/api/v1/fitness"),
  setGoal: (km: number | null) => api<{ goal_km: number | null }>("/api/v1/fitness/goal", { method: "PUT", body: JSON.stringify({ weekly_km: km }) }),
  upkeep: () => api<Upkeep>("/api/v1/hub/upkeep"),
  update: () => api<{ requested?: boolean; version?: string; detail?: string }>("/api/v1/hub/upkeep/update", { method: "POST" }),
  checkUpdate: () => api<{ latest?: string; update?: boolean; running?: string }>("/api/v1/hub/upkeep/check", { method: "POST" }),
};
