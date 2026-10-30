import { api } from "./client";

export interface SetupItem {
  id: string;
  title: string;
  area: string;
  state: "on" | "off" | "problem";
  detail: string;
  fix: string;
  settings: string[];
  link: string | null;
}

export interface Setup { items: SetupItem[]; counts: { on: number; off: number; problem: number }; checked_at: string }

export const setup = { get: () => api<Setup>("/api/v1/setup") };
