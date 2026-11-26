import { api } from "./client";

/** 11.11: the running version against main's on GitHub, and the last update's log. */
export interface Updates { current: string; latest: string | null; newer: boolean; headline: string; notes: string | null; error: string | null; log: string[] }

export const updates = {
  get: (fresh = false) => api<Updates>(`/api/v1/updates${fresh ? "?fresh=1" : ""}`),
  /** The Terminal shortcut that runs make update on the server (behind a fresh 2FA code). */
  command: "builtin:update-sirisos",
};
