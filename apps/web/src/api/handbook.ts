import { api, json } from "./client";

/** One of your own handbook commands (11.9), kept on the server. */
export interface HandbookEntry { id: string; cmd: string; what: string; section: string }

const H = "/api/v1/handbook";
export const handbook = {
  list: () => api<{ entries: HandbookEntry[] }>(H),
  add: (e: { cmd: string; what: string; section?: string }) => api<{ entries: HandbookEntry[] }>(H, json(e)),
  change: (id: string, e: Partial<Omit<HandbookEntry, "id">>) => api<{ entries: HandbookEntry[] }>(`${H}/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(e) }),
  remove: (id: string) => api<{ entries: HandbookEntry[] }>(`${H}/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
