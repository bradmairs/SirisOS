import { api, request } from "./client";

export type StepStatus = "todo" | "doing" | "done" | "na";
export type CpdCategory = "area" | "risk" | "business" | "other";

export interface Step { id: string; title: string; detail: string; status: StepStatus; note: string; done_on: string | null }
export interface Pathway { id: string; name: string; body: string; url: string; summary: string; steps: Step[] }
export interface Element { id: string; unit: string; title: string }
export interface EvidenceLink { label: string; url: string }
export interface Evidence { id: string; title: string; summary: string; date: string | null; elements: string[]; links: EvidenceLink[] }
export interface Goal { id: string; title: string; target_date: string | null; next_step: string; status: "active" | "done" | "paused"; note: string }
export interface CpdRecord {
  id: string; date: string | null; title: string; provider: string; type: string; hours: number;
  split: Partial<Record<CpdCategory, number>>; basis: "export" | "guess" | "you"; notes: string;
}
export interface CpdImport { at: string; filename: string; added: number; updated: number; unchanged: number }
export interface Profile { discipline: string; area_of_practice: string; brain_notes: string[] }

export interface CareerDocument {
  profile: Profile;
  pathways: Pathway[];
  elements: Element[];
  evidence: Evidence[];
  goals: Goal[];
  cpd: { records: CpdRecord[]; imports: CpdImport[]; overrides: Record<string, CpdCategory> };
  updated_at: string | null;
}

export interface CpdSummary {
  window: { from: string; to: string; years: number };
  total: number;
  required: number;
  short: number;
  met: boolean;
  categories: Record<CpdCategory, number>;
  minimums: { category: CpdCategory; label: string; hours: number; minimum: number; short: number }[];
  by_year: Record<string, number>;
  expiring_90_days: number;
  guessed: number;
  records: number;
  last_import: CpdImport | null;
  latest_activity: string | null;
}

export interface CareerOverview {
  cpd: CpdSummary;
  pathways: { id: string; name: string; done: number; total: number; next: { id: string; title: string; status: StepStatus } | null }[];
  competencies: { total: number; evidenced: number; counts: Record<string, number>; gaps: Element[] };
  goals: Goal[];
  next_steps: { title: string; detail: string; kind: "pathway" | "goal" | "cpd" | "evidence" }[];
  categories: Record<CpdCategory, string>;
}

export interface Career { document: CareerDocument; overview: CareerOverview }

export const career = {
  get: () => api<Career>("/api/v1/career"),
  overview: () => api<CareerOverview>("/api/v1/career/overview"),
  save: (doc: CareerDocument) =>
    api<Career>("/api/v1/career", {
      method: "PUT",
      body: JSON.stringify({ profile: doc.profile, pathways: doc.pathways, evidence: doc.evidence, goals: doc.goals }),
    }),
  importCpd: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const r = await request("/api/v1/career/cpd/import", { method: "POST", body: form });
    return (await r.json()) as Career & { import: CpdImport };
  },
  recategorise: (id: string, category: CpdCategory | null) =>
    api<Career>(`/api/v1/career/cpd/${encodeURIComponent(id)}/category`, { method: "PUT", body: JSON.stringify({ category }) }),
};

export const EA_PORTAL = "https://portal.engineersaustralia.org.au/";
