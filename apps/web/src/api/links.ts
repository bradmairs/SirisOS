import { api, request } from "./client";

export interface LinkItem {
  id: string;
  name: string;
  url: string;
  icon?: string | null;
  note?: string;
}

export interface LinkGroup {
  id: string;
  name: string;
  links: LinkItem[];
}

export interface LinksDocument {
  groups: LinkGroup[];
  updated_at?: string | null;
}

export interface LinkStatus {
  up: boolean;
  status: number | null;
  ms: number | null;
  error?: string;
}

export const links = {
  get: () => api<LinksDocument>("/api/v1/links"),
  save: (doc: LinksDocument) =>
    request("/api/v1/links", { method: "PUT", body: JSON.stringify(doc) }).then((r) => r.json() as Promise<LinksDocument>),
  status: () => api<Record<string, LinkStatus>>("/api/v1/links/status"),
};

export const newId = () => Math.random().toString(36).slice(2, 14);
