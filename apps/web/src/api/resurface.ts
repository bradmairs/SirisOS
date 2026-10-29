import { api, json } from "./client";

export interface ResurfacedNote {
  date: string;
  title: string;
  path: string | null;
  tags: string[];
  excerpt: string;
  why: string;
  as_of: string | null;
  age_days: number | null;
}

export const resurface = {
  today: () => api<{ note: ResurfacedNote | null }>("/api/v1/resurface"),
  respond: (title: string, answer: "seen" | "not_useful") => api<{ note: ResurfacedNote | null }>("/api/v1/resurface/respond", json({ title, answer })),
};

/** "8 months ago", "a year ago". */
export function ago(days: number | null): string | null {
  if (days == null) return null;
  if (days < 60) return `${Math.round(days / 7)} weeks ago`;
  if (days < 365) return `${Math.round(days / 30)} months ago`;
  const years = Math.round(days / 365);
  return years === 1 ? "a year ago" : `${years} years ago`;
}
