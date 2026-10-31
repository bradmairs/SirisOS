import { api } from "./client";

/** The standby killer (6.4): plugs off overnight and when nobody's home. */
export interface Standby {
  switches: string[];
  hours: string;
  suggestions: { sensor: string; name: string; watts: number; switch: string }[];
  off_now: string[];
}

export const standby = {
  get: () => api<Standby>("/api/v1/standby"),
  set: (switches: string[]) => api<{ switches: string[] }>("/api/v1/standby", { method: "PUT", body: JSON.stringify({ switches }) }),
};
