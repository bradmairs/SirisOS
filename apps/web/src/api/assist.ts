import { api, json } from "./client";

/** 11.3: smart capture, the day's plan, Home learning, patterns, goals steering and while you were away. */

export interface Routed { handled: boolean; kind?: string; where?: string | null; url?: string; said?: string; error?: string; undo?: Record<string, unknown> | null }
export const capture = {
  route: (text: string) => api<Routed>("/api/v1/capture/route", json({ text })),
  undo: (undo: Record<string, unknown>) => api<{ undone: boolean }>("/api/v1/capture/undo", json({ undo })),
};

export interface PlanBlock { start: string; end: string; minutes: number; kind: "deep" | "quick" | "normal" | "errand" | "set" | "goal"; title: string; task_id: string | null; area: string | null; goal?: string }
export interface DayPlan { date: string; readiness: number | null; until: string; blocks: PlanBlock[]; left: { id: string; title: string; why: string }[]; free_minutes: number; tasks: number; events: { start: string; end: string }[] }
export const plan = { today: () => api<DayPlan>("/api/v1/plan/today") };

export interface Usage { on: boolean; phases: Record<string, Record<string, { score: number; tucked: boolean; seen_days: number; taps: number }>>;
  /** 11.9: sections you usually open at each part of the day, and days each section was opened in four weeks. */
  usually?: Record<string, { path: string; days: number }[]>; sections?: Record<string, number> }
export const usage = {
  get: () => api<Usage>("/api/v1/home/usage"),
  send: (events: { phase: string; widget: string; kind: "seen" | "tap" | "visit"; interactive?: boolean }[]) => api<{ ok: boolean }>("/api/v1/home/usage", json({ events })),
  setOn: (on: boolean) => api<Usage>("/api/v1/home/usage", { method: "PUT", body: JSON.stringify({ on }) }),
};

export interface Pattern { id: string; text: string; try: string | null; strength: number; worse: boolean; days: number }
export interface Patterns { at: string; patterns: Pattern[]; days: number; sources: string[] }
export const patterns = { get: () => api<Patterns>("/api/v1/patterns") };

export interface SteerGoal {
  id: string; title: string; state: string; value: number | null; target: number | null; unit: string;
  projected: number | null; projected_percent: number | null; weekly: number | null; weeks_left: number; step: { text: string } | null;
}
export const steer = { get: () => api<{ year: number; through_year: number; goals: SteerGoal[]; behind: SteerGoal[] }>("/api/v1/goals/steer") };

export interface AwayItem { kind: string; title: string; lines: string[]; url: string }
export interface Away { away: boolean; since?: string; away_for?: string; items?: AwayItem[]; keys?: string[] }
export const away = {
  get: () => api<Away>("/api/v1/away"),
  done: (keys: string[]) => api<{ ok: boolean }>("/api/v1/away/done", json({ keys })),
  touch: () => api<{ ok: boolean }>("/api/v1/away/touch", { method: "POST" }),
};
