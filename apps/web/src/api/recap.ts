import { api } from "./client";

/** 10.2: last month in short. */
export interface Recap {
  month: string; title: string; text: string; filed_as: string | null; seen: boolean; show: boolean;
  money: { spent: number | null; planned: number; over: string[]; net_worth: number | null; net_worth_change: number | null; currency: string } | null;
  health: Record<string, { value: number; before: number | null; word?: string }> | null;
  work: { timesheet_hours: number; cpd_hours: number };
  habits: { name: string; kept: number; of: number; rate: number }[];
}
export const recap = {
  get: (month?: string) => api<Recap>(`/api/v1/recap${month ? `?month=${month}` : ""}`),
  seen: (month: string) => api<{ seen: boolean }>(`/api/v1/recap/${month}/seen`, { method: "POST" }),
};
