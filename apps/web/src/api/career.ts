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
  next_steps: { title: string; detail: string; kind: "pathway" | "goal" | "cpd" | "evidence" | "application" }[];
  application: { percent: number; done: number; total: number };
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
  plan: () => api<CpdPlan>("/api/v1/career/cpd/plan"),
  suggestions: () => api<{ suggestions: CpdSuggestion[]; unavailable: boolean; guest_mode: boolean }>("/api/v1/career/cpd/suggestions"),
  markSuggestion: (key: string, status: "logged" | "ignored") =>
    api<{ key: string; status: string }>(`/api/v1/career/cpd/suggestions/${encodeURIComponent(key)}`, { method: "POST", body: JSON.stringify({ status }) }),
  recategorise: (id: string, category: CpdCategory | null) =>
    api<Career>(`/api/v1/career/cpd/${encodeURIComponent(id)}/category`, { method: "PUT", body: JSON.stringify({ category }) }),
};

export interface PacingRow {
  category: "total" | CpdCategory;
  label: string;
  target: number;
  staying: number;
  need: number;
  per_month: number;
  last_12_months: number;
  on_track: boolean;
}

export interface CpdPlan {
  on_track: boolean;
  rows: PacingRow[];
  gaps: { category: string; label: string; short: number; tip: string; courses: { title: string; subtitle: string; url: string | null; kind: string }[] }[];
}

export interface CpdSuggestion {
  key: string;
  title: string;
  date: string | null;
  upcoming: boolean;
  hours: number;
  category: CpdCategory;
  location: string | null;
  calendar: string | null;
}

export interface ClaimDraft {
  id: string;
  unit: string;
  title: string;
  note_title: string;
  evidence: number;
  markdown: string;
  prose: string | null;
  prose_available: boolean;
}

export const claims = {
  draft: (id: string, prose = false) => api<ClaimDraft>(`/api/v1/career/claims/${encodeURIComponent(id)}${prose ? "?prose=true" : ""}`),
  save: (id: string, markdown: string) =>
    api<{ saved: boolean; title: string; action?: string }>(`/api/v1/career/claims/${encodeURIComponent(id)}/save`, {
      method: "POST",
      body: JSON.stringify({ markdown }),
    }),
};

export const EA_PORTAL = "https://portal.engineersaustralia.org.au/";

export type FormId = "cpd" | "reflection" | "bia";
export type BiaState = "VIC" | "WA" | "ACT";

export interface ApplicationAnswers {
  area_of_practice: string;
  additional_area: string;
  additional_reason: string;
  cpd_evidence: "log" | "questionnaire" | null;
  cpd_answers: Record<string, string>;
  part1: Record<string, "yes" | "not_sure">;
  part2: Record<string, "yes" | "no">;
  part3: Record<string, string>;
  signed: boolean;
  bia: { required: boolean | null; state: BiaState | null; cv: boolean; building_cpd: boolean; statement: string };
  files: Partial<Record<FormId, { filename: string; size: number; at: string }>>;
}

export interface ApplicationView {
  application: ApplicationAnswers;
  documents: { id: FormId; title: string; form: string; summary: string }[];
  cpd_questions: { id: string; q: string; type: string }[];
  part1: { id: string; q: string; elements: string[] }[];
  part2: { id: string; q: string }[];
  elements: (Element & { meaning: string })[];
  bia_states: Record<BiaState, { name: string; years: number; laws: string }>;
  readiness: {
    percent: number; done: number; total: number;
    items: { id: string; label: string; done: boolean; detail: string }[];
    prepare: { id: string; q: string; elements: string[] }[];
    /** How well each element is evidenced (6.3), weakest first. */
    elements?: ElementStrength[];
    strength?: { solid: number; thin: number; none: number };
  };
}

export interface ElementStrength { id: string; unit: string; title: string; strength: "none" | "thin" | "solid"; evidence: string[]; linked: number; words: number; next: string | null }

const A = "/api/v1/career/application";

export const application = {
  get: () => api<ApplicationView>(A),
  save: (answers: ApplicationAnswers) => {
    const edit: Partial<ApplicationAnswers> = { ...answers };
    delete edit.files;
    return api<ApplicationView>(A, { method: "PUT", body: JSON.stringify(edit) });
  },
  draftCpd: (id: string) => api<{ id: string; text: string }>(`${A}/draft/cpd/${encodeURIComponent(id)}`),
  draftElement: (id: string) => api<{ id: string; text: string }>(`${A}/draft/element/${encodeURIComponent(id)}`),
  upload: async (form: FormId, file: File) => {
    const body = new FormData();
    body.append("file", file);
    const r = await request(`${A}/${form}/file`, { method: "POST", body });
    return (await r.json()) as ApplicationView;
  },
  async download(form: FormId, filename: string) {
    const url = URL.createObjectURL(await (await request(`${A}/${form}/file`)).blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: filename });
    a.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
  },
  remove: (form: FormId) => api<ApplicationView>(`${A}/${form}/file`, { method: "DELETE" }),
};
