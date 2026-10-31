import { api, json, request } from "./client";

export interface Contributor { key: string; label: string; unit: string; value: number | null; baseline: number | null; score: number; text: string }
export interface Readiness {
  date: string;
  score: number;
  band: "Primed" | "Steady" | "Recover";
  advice: string;
  early: boolean;
  contributors: Contributor[];
  summary: string;
  /** 5.9 (SirisAI 3.62): kept as it was this morning, so the day's HRV, a workout or a nap don't move it. */
  locked?: boolean;
  locked_at?: string;
}
/** The day's energy (5.9, SirisAI 3.62): a Body Battery that starts from readiness at waking. */
export interface Energy {
  now: number;
  start: number;
  wake: string;
  timeline: { time: string; value: number }[];
  spent: { awake: number; activity: number; stress: number };
  regained: number;
  summary: string;
  /** No hourly data (Health Auto Export aggregated by day): worked out from the day's totals. */
  estimated: boolean;
}
/** Strain 0-21 (6.4, SirisAI 4.03): today against a target from readiness. */
export interface Strain {
  today: number; target: [number, number]; status: "under" | "in range" | "over"; advice: string; max_hr: number;
  workouts: { name: string | null; start: string | null; minutes: number | null; strain: number }[];
  week: { date: string; strain: number }[];
}
/** The week's sleep in one report (6.4). */
export interface SleepWeek {
  nights: number; average: number | null; need: number; debt: number; bedtime_spread_min: number | null; short_nights: number;
  best: { date: string; hours: number }; worst: { date: string; hours: number }; factors: string[]; tip: string;
}
/** Is Health Auto Export set up right (6.4)? Each problem names the setting to change. */
export interface HealthSetup {
  connected: boolean; problems: string[];
  metrics?: { at: string; aggregation?: string; days_covered?: number } | null;
  workouts?: { at: string; days_covered?: number } | null;
}
export interface Trend { key: string; label: string; unit: string; week: number; baseline: number; change_pct: number; direction: "up" | "down" | "steady"; good: boolean | null }
export interface Night { date: string; hours: number | null; deep: number | null; rem: number | null; core: number | null; awake: number | null; in_bed: number | null; start: string | null; end: string | null }
export interface Point { date: string; value: number | null }
export interface Vital { key: string; label: string; unit: string; value: number; date: string; baseline: number | null; spread: number | null; state: "normal" | "high" | "low"; series: Point[] }
export interface Workout { date: string; name: string; start: string; minutes: number | null; km: number | null; kcal: number | null; avg_hr: number | null; max_hr: number | null }

export interface WeightTrend { latest: number; latest_date: string; trend: number; per_week: number; goal_kg?: number; to_go_kg?: number; weeks_to_goal?: number | null; series: { date: string; weight: number; trend: number }[] }
export interface Insight { factor: string; minutes: number; nights_with: number; nights_without: number; text: string }
export interface Bedtime { bedtime: string; wake: string; sleep_target_h: number; debt_7d: number; because: string; text: string }
export interface HealthNote { id: number; day: string; kind: string; text: string; at: string }
export interface Goal { goal_id: number; metric: string; target: number; start: string; end: string; title: string; done: number; expected_by_now: number; percent: number | null; on_pace: boolean; needed_per_week: number | null }

export interface Health {
  today: string;
  available: boolean;
  guest_mode?: boolean;
  /** SirisOS's old store is still being moved into SirisAI (5.8). */
  migrating?: boolean;
  sources: { sirisai: boolean; health_auto_export: boolean; days: number; imports?: Record<string, { at: string; days?: number }> };
  readiness: Readiness | null;
  energy?: Energy | null;
  strain?: Strain | null;
  sleep_week?: SleepWeek | null;
  setup?: HealthSetup | null;
  sleep: { need: number; last_night: Night | null; score: number | null; debt_7d: number; bedtime_spread_min: number | null; average_7d: number | null; nights: Night[] };
  activity: {
    steps: number | null; active_energy_kcal: number | null; exercise_minutes: number | null; stand_hours: number | null;
    load: { acute_min_per_day: number; chronic_min_per_day: number; ratio: number | null; zone: "low" | "sweet spot" | "building" | "spike" | null };
    exercise_series: Point[]; steps_series: Point[]; workouts: Workout[];
  };
  vitals: Vital[];
  /** 5.8, from SirisAI 3.51 */
  weight?: WeightTrend | null;
  /** `early` (6.1, SirisAI 3.82): two signs today alone; `likely`: two days running. */
  getting_sick?: { date: string; today: string[]; yesterday: string[]; level?: "early" | "likely" } | null;
  /** This week against your last 30 days (6.1). */
  trends?: Trend[];
  logged?: { water_ml: number | null; caffeine_mg: number | null; alcohol_drinks: number | null; mood: number | null; notes: HealthNote[] } | null;
  insights?: Insight[];
  bedtime?: Bedtime | null;
}

export type LogKind = "water" | "caffeine" | "alcohol" | "mood" | "energy" | "symptom" | "supplement" | "medication" | "feeling" | "note";

async function upload<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  const r = await request(path, { method: "POST", body });
  return (await r.json()) as T;
}

export const health = {
  get: () => api<Health>("/api/v1/health"),
  today: () => api<{ readiness: Readiness | null; energy?: Energy | null }>("/api/v1/health/today"),
  log: (kind: LogKind, amount?: number, text?: string) => api<{ logged: unknown }>("/api/v1/health/log", json({ kind, amount, text: text ?? "" })),
  meal: (file: File) => upload<{ kcal: number; protein_g: number | null; note: HealthNote }>("/api/v1/health/meal", file),
  goals: () => api<{ goals: Goal[] }>("/api/v1/health/goals"),
  addGoal: (goal: { metric: string; target: number; end: string; start?: string; title?: string }) => api<{ goal: Goal }>("/api/v1/health/goals", json(goal)),
  backfill: (file: File) => upload<{ source: string; days: number; readings: number; workouts: number; from: string | null }>("/api/v1/health/apple-export", file),
  remove: (start: string, end: string, source = "") =>
    api<{ readings: number; workouts: number }>(`/api/v1/health/data?${new URLSearchParams({ start, end, ...(source ? { source } : {}) })}`, { method: "DELETE" }),
  async download(path: string, filename: string) {
    const url = URL.createObjectURL(await (await request(path)).blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: filename });
    a.click();
    URL.revokeObjectURL(url);
  },
  async report() {
    const html = await (await request("/api/v1/health/report?days=90")).text();
    const w = window.open("", "_blank");
    if (w) { w.document.write(html); w.document.close(); }
  },
};

export const BAND_TONE: Record<Readiness["band"], string> = { Primed: "tone-good", Steady: "tone-warning", Recover: "tone-critical" };
