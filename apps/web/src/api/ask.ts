import { api } from "./client";

/** Ask Siris from a Shortcut (11.16): a key for the Shortcut, shown once. */
export const askKey = {
  get: () => api<{ on: boolean; made: string | null }>("/api/v1/ask/key"),
  make: () => api<{ key: string; url: string }>("/api/v1/ask/key", { method: "POST" }),
  drop: () => api<{ on: boolean }>("/api/v1/ask/key", { method: "DELETE" }),
};
