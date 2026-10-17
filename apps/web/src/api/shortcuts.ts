import { api, json } from "./client";

export type ShortcutScope = "capture" | "ask" | "today" | "protocols";

export interface ShortcutKey {
  id: string;
  label: string;
  scopes: ShortcutScope[];
  created_at: string;
  last_used: string | null;
}

export const shortcuts = {
  keys: () => api<{ keys: ShortcutKey[]; scopes: ShortcutScope[] }>("/api/v1/shortcuts/keys"),
  create: (label: string, scopes: ShortcutScope[]) => api<ShortcutKey & { secret: string }>("/api/v1/shortcuts/keys", json({ label, scopes })),
  revoke: (id: string) => api<{ revoked: boolean }>(`/api/v1/shortcuts/keys/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
