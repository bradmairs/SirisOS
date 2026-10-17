import { api } from "./client";
import type { AppStatus } from "./types";

type State = "ok" | "degraded" | "down";

export interface AppHealth {
  id: string;
  name: string;
  icon: string;
  status: AppStatus;
  samples: number;
  uptime_24h: number | null;
  uptime_7d: number | null;
  latency_ms_24h: number | null;
  /** Last 24 hours, oldest first: the worst state each hour, or null with no check. */
  hours: (State | null)[];
  days: (State | null)[];
  last_problem: { at: number; state: State; detail: string } | null;
  incidents: { at: number; detail: string; minutes: number | null }[];
}

export const systemStatus = {
  get: () => api<{ apps: AppHealth[]; sample_every_minutes: number }>("/api/v1/hub/status"),
};
