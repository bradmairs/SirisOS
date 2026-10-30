import { api } from "./client";

export interface Contributor { key: string; label: string; unit: string; value: number | null; baseline: number | null; score: number; text: string }
export interface Readiness {
  date: string;
  score: number;
  band: "Primed" | "Steady" | "Recover";
  advice: string;
  early: boolean;
  contributors: Contributor[];
  summary: string;
}
export interface Night { date: string; hours: number | null; deep: number | null; rem: number | null; core: number | null; awake: number | null; in_bed: number | null; start: string | null; end: string | null }
export interface Point { date: string; value: number | null }
export interface Vital { key: string; label: string; unit: string; value: number; date: string; baseline: number | null; spread: number | null; state: "normal" | "high" | "low"; series: Point[] }
export interface Workout { date: string; name: string; start: string; minutes: number | null; km: number | null; kcal: number | null; avg_hr: number | null; max_hr: number | null }

export interface Health {
  today: string;
  available: boolean;
  sources: { sirisai: boolean; health_auto_export: boolean; days: number };
  readiness: Readiness | null;
  sleep: { need: number; last_night: Night | null; score: number | null; debt_7d: number; bedtime_spread_min: number | null; average_7d: number | null; nights: Night[] };
  activity: {
    steps: number | null; active_energy_kcal: number | null; exercise_minutes: number | null; stand_hours: number | null;
    load: { acute_min_per_day: number; chronic_min_per_day: number; ratio: number | null; zone: "low" | "sweet spot" | "building" | "spike" | null };
    exercise_series: Point[]; steps_series: Point[]; workouts: Workout[];
  };
  vitals: Vital[];
}

export const health = {
  get: () => api<Health>("/api/v1/health"),
  today: () => api<{ readiness: Readiness | null }>("/api/v1/health/today"),
};

export const BAND_TONE: Record<Readiness["band"], string> = { Primed: "tone-good", Steady: "tone-warning", Recover: "tone-critical" };
