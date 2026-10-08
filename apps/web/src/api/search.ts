import { api } from "./client";

export interface SearchHit {
  title: string;
  subtitle: string;
  /** A SirisOS route ("/brain?q=…") or, when `external`, another app's page. */
  url: string | null;
  external: boolean;
  kind: string;
  /** Set for app results: opens that app's status sheet. */
  app_id: string | null;
  score: number;
}

export interface SearchGroup {
  id: string;
  label: string;
  icon: string;
  hits: SearchHit[];
  best: number;
}

export interface SearchResponse {
  query: string;
  groups: SearchGroup[];
  /** Sources that didn't answer in time. */
  failed: string[];
  took_ms: number;
}

export const search = {
  everything: (q: string, signal?: AbortSignal) => api<SearchResponse>(`/api/v1/search?q=${encodeURIComponent(q)}`, { signal }),
};
