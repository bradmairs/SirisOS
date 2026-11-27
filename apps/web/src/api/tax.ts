import { api, json, request } from "./client";
import { nameFrom } from "./save";

/** Tax-claimable receipts (11.18), by Australian financial year (named by the year it ends: 2027 is 2026-27). */
export interface TaxClaim {
  id: string; date: string; vendor: string; description: string; category: string; amount: number; work_pct: number;
  reimbursed: boolean; has_receipt: boolean; set_item?: boolean; doc_id?: number | null; note?: string; source: "email" | "manual";
  claimable: number; treatment: "deduct" | "depreciate" | "check" | "none"; treatment_note: string; work: boolean;
}
export interface TaxToSort { doc_id: number; date: string; vendor: string; description: string; amount: number | null; category: string }
export interface TaxYear {
  fy: number; label: string; start: string; end: string; claims: TaxClaim[];
  by_category: { category: string; label: string; count: number; claimable: number; depreciate: number }[];
  wfh: { hours: number; rate: number; claimable: number }; car: { km: number; rate: number; cap: number; claimable: number };
  work_total: number; total: number; missing_receipts: string[]; checks: { level: "ok" | "info" | "warn"; text: string }[];
  to_sort: TaxToSort[]; years: number[]; categories: { id: string; label: string; hint: string }[]; email_problem: string | null;
}
export type TaxClaimInput = Partial<Omit<TaxClaim, "id" | "claimable" | "treatment" | "treatment_note" | "work" | "source">>;

const T = "/api/v1/tax";
export const tax = {
  year: (fy?: number) => api<TaxYear>(`${T}${fy ? `?fy=${fy}` : ""}`),
  add: (c: TaxClaimInput) => api<TaxClaim>(`${T}/claims`, json(c)),
  change: (id: string, c: TaxClaimInput) => api<TaxClaim>(`${T}/claims/${id}`, { ...json(c), method: "PUT" }),
  remove: (id: string) => api<{ ok: boolean }>(`${T}/claims/${id}`, { method: "DELETE" }),
  notTax: (docId: number, on = true) => api<{ ok: boolean }>(`${T}/not-tax/${docId}${on ? "" : "?on=false"}`, { method: "POST" }),
  setYear: (fy: number, body: { wfh_hours?: number; car_km?: number }) => api<Record<string, number>>(`${T}/years/${fy}`, { ...json(body), method: "PUT" }),
  export: async (fy: number) => {
    const r = await request(`${T}/export?fy=${fy}`);
    return { blob: await r.blob(), name: nameFrom(r.headers.get("content-disposition"), `Tax claims ${fy}.csv`) };
  },
};
