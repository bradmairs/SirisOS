import { api, json } from "./client";
import type { TaskItem } from "./tasks";

export interface WrapMeeting {
  title: string;
  start: string | null;
  end: string | null;
  location: string | null;
  cpd: { key: string; title: string; hours: number; category: string } | null;
}

export interface WrapUpOverview {
  date: string;
  done: { id: string; title: string }[];
  open: TaskItem[];
  meetings: WrapMeeting[];
  calendar_unavailable: boolean;
  suggested_top3: string[];
  saved: { top3: string[]; journal: string; journal_saved_as: string | null; at: string } | null;
}

export const wrapup = {
  get: () => api<WrapUpOverview>("/api/v1/wrapup"),
  save: (top3: string[], journal: string) => api<NonNullable<WrapUpOverview["saved"]>>("/api/v1/wrapup", json({ top3, journal })),
  logCpd: (key: string, title: string, hours: number) => api<{ key: string; task: { title: string } }>(`/api/v1/wrapup/cpd/${encodeURIComponent(key)}`, json({ title, hours })),
  notCpd: (key: string) => api(`/api/v1/career/cpd/suggestions/${encodeURIComponent(key)}`, json({ status: "ignored" })),
};
