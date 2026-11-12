import { api } from "./client";

/** Add to SirisOS from the Share Sheet (8.9): a key for the Shortcut, shown once. */
export const shareKey = {
  get: () => api<{ on: boolean; made: string | null }>("/api/v1/share/key"),
  make: () => api<{ key: string; url: string }>("/api/v1/share/key", { method: "POST" }),
  drop: () => api<{ on: boolean }>("/api/v1/share/key", { method: "DELETE" }),
};
