import { api, json, request } from "./client";
import type { Result } from "../engineering/calculators";

export interface EvidenceItem {
  document_id: string;
  title: string;
  authority: string;
  reference: string | null;
  edition: string | null;
  page: number;
  citation: string;
  excerpt: string;
  score: number;
}

export interface EvidenceResponse {
  question: string;
  sufficient_evidence: boolean;
  evidence: EvidenceItem[];
  context_text: string;
  guidance: string;
  retrieval_strategy: string;
  synthesized_answer: string | null;
}

export interface HydroHistory {
  id: string;
  question: string;
  sufficient_evidence: boolean;
  citations: string[];
  synthesized_answer: string | null;
  created_at: string;
}

export interface StandardDocument {
  id: string;
  title: string;
  authority: string;
  reference: string | null;
  edition: string | null;
  filename: string;
  uploaded_at: string;
  pages: number;
  indexed: boolean;
  extraction_method: string;
  ocr_attempted: boolean;
  ocr_error: string | null;
  active: boolean;
  archived_at: string | null;
  supersedes_id: string | null;
  superseded_by_id: string | null;
  revision: number;
}

export interface StandardHit {
  document: StandardDocument;
  page: number | null;
  snippet: string | null;
  score: number | null;
  citation: string | null;
}

export interface StandardPage {
  document: StandardDocument;
  page: number;
  text: string;
  citation: string;
}

export interface Calculation {
  id: string;
  calculator_id: string;
  title: string;
  inputs: Record<string, number>;
  results: Result[];
  notes: string;
  cited_standard_id: string | null;
  cited_standard_label: string | null;
  created_at: string;
}

export type ProjectKind = "engineering" | "homelab" | "travel" | "fitness" | "personal" | "other";
export type ProjectStatus = "active" | "paused" | "completed" | "archived";

export interface Project {
  id: string;
  name: string;
  description: string;
  kind: ProjectKind;
  status: ProjectStatus;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface Relationship {
  id: string;
  project_id: string;
  target_type: "knowledge_note" | "engineering_standard" | "calculation";
  target_id: string;
  target_label: string;
  kind: "contains" | "references";
  provenance: string;
  created_at: string;
}

const E = "/api/v1/engineering";
const qs = (params: Record<string, string | number | boolean | undefined | null>) =>
  new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => [k, String(v)])).toString();

export const hydro = {
  ask: (question: string, limit = 6) => api<EvidenceResponse>(`${E}/sirishydro/evidence?${qs({ question, limit })}`),
  history: () => api<{ history: HydroHistory[] }>(`${E}/sirishydro/history`).then((r) => r.history),
  remove: (id: string) => api<void>(`${E}/sirishydro/history/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

export const standards = {
  search: (opts: { query?: string; authority?: string; includeArchived?: boolean; limit?: number } = {}) =>
    api<{ query: string; hits: StandardHit[] }>(
      `${E}/standards?${qs({ query: opts.query, authority: opts.authority, include_archived: opts.includeArchived, limit: opts.limit ?? 50 })}`,
    ).then((r) => r.hits),
  upload: (file: File, meta: { title: string; authority: string; reference?: string; edition?: string }, replaceId?: string) => {
    const form = new FormData();
    form.append("file", file);
    for (const [k, v] of Object.entries(meta)) if (v) form.append(k, v);
    return api<StandardDocument>(replaceId ? `${E}/standards/${encodeURIComponent(replaceId)}/replace` : `${E}/standards`, { method: "POST", body: form });
  },
  archive: (id: string) => api<StandardDocument>(`${E}/standards/${encodeURIComponent(id)}`, { method: "DELETE" }),
  restore: (id: string) => api<StandardDocument>(`${E}/standards/${encodeURIComponent(id)}/restore`, { method: "POST" }),
  page: (id: string, page: number) => api<StandardPage>(`${E}/standards/${encodeURIComponent(id)}/pages/${page}`),
  /** The PDF needs the bearer token, so fetch it and open a blob URL. */
  async openFile(id: string, page?: number) {
    const target = window.open("", "_blank");
    const blob = await (await request(`${E}/standards/${encodeURIComponent(id)}/file`)).blob();
    const url = URL.createObjectURL(blob) + (page ? `#page=${page}` : "");
    if (target) target.location.href = url;
    else window.location.href = url;
  },
};

export const calculations = {
  list: () => api<{ calculations: Calculation[] }>(`${E}/calculations`).then((r) => r.calculations),
  save: (body: { calculator_id: string; title: string; inputs: Record<string, number>; results: Result[]; notes?: string; cited_standard_id?: string | null }) =>
    api<Calculation>(`${E}/calculations`, json(body)),
  remove: (id: string) => api<void>(`${E}/calculations/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

const P = "/api/v1/projects";
export const projects = {
  list: () => api<{ projects: Project[] }>(P).then((r) => r.projects),
  get: (id: string) => api<Project>(`${P}/${encodeURIComponent(id)}`),
  create: (body: { name: string; description?: string; kind?: ProjectKind; tags?: string[] }) => api<Project>(P, json(body)),
  update: (id: string, body: Partial<Pick<Project, "name" | "description" | "kind" | "status" | "tags">>) =>
    api<Project>(`${P}/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(body) }),
  current: () => api<{ project: Project | null; selected_at: string | null }>(`${P}/current`),
  setCurrent: (projectId: string | null) => api<{ project: Project | null }>(`${P}/current`, { method: "PUT", body: JSON.stringify({ project_id: projectId }) }),
  relationships: (id: string) => api<{ relationships: Relationship[] }>(`${P}/${encodeURIComponent(id)}/relationships`).then((r) => r.relationships),
  link: (id: string, body: { target_type: Relationship["target_type"]; target_id: string; kind: Relationship["kind"] }) =>
    api<Relationship>(`${P}/${encodeURIComponent(id)}/relationships`, json(body)),
  unlink: (id: string, relationshipId: string) =>
    api<void>(`${P}/${encodeURIComponent(id)}/relationships/${encodeURIComponent(relationshipId)}`, { method: "DELETE" }),
};
