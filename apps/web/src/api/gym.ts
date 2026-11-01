import { api, json, request } from "./client";

export type Kind = "weight" | "bodyweight" | "time" | "cardio";
export interface Exercise { id: string; name: string; primary: string; secondary: string[]; equipment: string; kind: Kind; custom: boolean }
export interface SetLog { reps?: number | null; weight?: number | null; seconds?: number | null; km?: number | null; done: boolean; type: "normal" | "warmup" | "drop" | "failure"; rpe?: number | null }
export interface EntryLog { exercise: string; sets: SetLog[]; note?: string }
export interface Session { id: string; title: string; started_at: string; ended_at?: string | null; routine_id?: string | null; day?: number | null; entries: EntryLog[]; note?: string; bodyweight?: number | null }
export interface PlanExercise { exercise: string; sets: number; reps: string; rest_s: number; note?: string }
export interface RoutineDay { name: string; exercises: PlanExercise[] }
export interface Routine { id: string; name: string; days: RoutineDay[]; note?: string; active: boolean }
export interface GymSettings { unit: "kg"; bar: number; plates: number[]; increment: number; rest_s: number }
export interface Summary { id: string; title: string; date: string; started_at: string; minutes: number | null; sets: number; exercises: number; volume: number; names: string[] }
export interface Gym {
  settings: GymSettings; exercises: Exercise[]; routines: Routine[]; active: { routine: string; next_day: number } | null;
  recent: Summary[]; week: { week_of: string; sessions: number; sets_by_muscle: Record<string, number>; volume: number };
  streak_weeks: number; total_sessions: number;
}
export interface Plan { routine: string; day: number; title: string; exercises: (PlanExercise & { name: string; kind: Kind; last: SetLog[]; suggest: { weight: number | null; reps: number; why: string } })[] }
export interface GymRecord { exercise: string; name: string; kind: string; text: string }
export interface ExerciseDetail {
  exercise: Exercise;
  records: { heaviest?: { weight: number; reps: number | null; date: string }; e1rm?: { value: number; date: string }; rep_max?: Record<string, { weight: number; date: string }>;
    most_reps?: { reps: number; weight: number | null; date: string }; best_volume?: { volume: number; date: string } };
  series: { date: string; e1rm: number | null; best: number | null; volume: number; reps: number }[];
  history: { session: string; date: string; sets: SetLog[]; e1rm: number | null; volume: number }[];
}

export interface ImportPreview {
  sets: number; workouts: number; from: string | null; to: string | null; replacing: number;
  exercises: { name: string; sets: number; match: string | null; match_name: string | null; how: "exact" | "close" | "guess" | "none"; new_muscle: string }[];
}
/** What the weights in an import file are in; SirisGYM saves kilograms either way. */
export type ImportUnit = "auto" | "kg" | "lb";

const G = "/api/v1/gym";
async function importFile<T>(file: File, unit: ImportUnit, choices?: Record<string, string>): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  body.append("unit", unit);
  body.append("dry_run", choices ? "false" : "true");
  if (choices) body.append("choices", JSON.stringify(choices));
  const r = await request(`${G}/import`, { method: "POST", body });
  return (await r.json()) as T;
}
export const gym = {
  get: () => api<Gym>(G),
  settings: (s: GymSettings) => api<GymSettings>(`${G}/settings`, { method: "PUT", body: JSON.stringify(s) }),
  addExercise: (e: Pick<Exercise, "name" | "primary" | "secondary" | "equipment" | "kind">) => api<Exercise>(`${G}/exercises`, json(e)),
  exercise: (id: string) => api<ExerciseDetail>(`${G}/exercises/${encodeURIComponent(id)}`),
  templates: () => api<{ templates: Routine[] }>(`${G}/templates`),
  addRoutine: (body: { template?: string; routine?: Omit<Routine, "id"> & { id?: string } }) => api<Routine>(`${G}/routines`, json(body)),
  saveRoutine: (r: Routine) => api<Routine>(`${G}/routines/${r.id}`, { method: "PUT", body: JSON.stringify(r) }),
  deleteRoutine: (id: string) => api<{ deleted: string }>(`${G}/routines/${id}`, { method: "DELETE" }),
  plan: (routine: string, day?: number) => api<Plan>(`${G}/plan?routine=${encodeURIComponent(routine)}${day != null ? `&day=${day}` : ""}`),
  finish: (s: Session) => api<{ summary: Summary; records: GymRecord[] }>(`${G}/sessions`, json(s)),
  sessions: (month?: string) => api<{ sessions: Summary[] }>(`${G}/sessions${month ? `?month=${month}` : ""}`),
  session: (id: string) => api<Omit<Session, "entries"> & { summary: Summary; records: GymRecord[]; entries: (EntryLog & { name: string })[] }>(`${G}/sessions/${id}`),
  importPreview: (file: File, unit: ImportUnit) => importFile<{ preview: ImportPreview }>(file, unit),
  importCommit: (file: File, unit: ImportUnit, choices: Record<string, string>) =>
    importFile<{ imported: { workouts: number; sets: number; new_exercises: number } }>(file, unit, choices),
  deleteSession: (id: string) => api<{ deleted: string }>(`${G}/sessions/${id}`, { method: "DELETE" }),
};

/** Estimated one-rep max (Epley), as the server works it out. */
export function e1rm(weight?: number | null, reps?: number | null): number | null {
  if (!weight || !reps || reps > 12) return null;
  return Math.round((reps === 1 ? weight : weight * (1 + reps / 30)) * 10) / 10;
}

/** The plates for each side, largest first. */
export function plates(target: number, bar: number, available: number[]): { perSide: number[]; left: number } {
  let rest = (target - bar) / 2;
  if (rest < 0) return { perSide: [], left: target - bar };
  const perSide: number[] = [];
  for (const p of [...available].sort((a, b) => b - a)) {
    while (rest >= p - 1e-9) { perSide.push(p); rest -= p; }
  }
  return { perSide, left: Math.round(rest * 200) / 100 };
}

/** The workout in progress lives on this phone until it's finished (gyms are often out of signal). */
const ACTIVE = "sirisos.gym.active";
export function loadActive(): Session | null {
  try { const raw = window.localStorage.getItem(ACTIVE); return raw ? (JSON.parse(raw) as Session) : null; } catch { return null; }
}
export function saveActive(s: Session | null): void {
  try { if (s) window.localStorage.setItem(ACTIVE, JSON.stringify(s)); else window.localStorage.removeItem(ACTIVE); } catch { /* storage off */ }
}
export function newId(): string {
  return Math.random().toString(16).slice(2, 14).padEnd(12, "0");
}
