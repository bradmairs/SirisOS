import { api, json } from "./client";

/** Documents and renewals (9.3): what expires that never arrives by email, with reminders before it does. */
export type RenewalKind = "passport" | "licence" | "rego" | "insurance" | "medicare" | "warranty" | "membership" | "other";
export interface Renewal { id: string; name: string; kind: RenewalKind; expires: string; note: string; days_left: number; state: "expired" | "soon" | "later" | "fine" }

const R = "/api/v1/renewals";
export const renewals = {
  list: () => api<{ renewals: Renewal[] }>(R),
  add: (r: { name: string; kind: RenewalKind; expires: string; note?: string }) => api<{ renewals: Renewal[] }>(R, json(r)),
  change: (id: string, c: Partial<Pick<Renewal, "name" | "kind" | "expires" | "note">>) =>
    api<{ renewals: Renewal[] }>(`${R}/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(c) }),
  remove: (id: string) => api<{ renewals: Renewal[] }>(`${R}/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
