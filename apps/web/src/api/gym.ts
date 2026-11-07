import { api, json, request } from "./client";

export type Kind = "weight" | "bodyweight" | "time" | "cardio";
export interface Exercise { id: string; name: string; primary: string; secondary: string[]; equipment: string; kind: Kind; custom: boolean }
export interface SetLog { reps?: number | null; weight?: number | null; seconds?: number | null; km?: number | null; done: boolean; type: "normal" | "warmup" | "drop" | "failure"; rpe?: number | null;
  /** When it was ticked done (6.96), to line it up with the Watch's heart rate. */
  at?: string | null }
export interface EffortExercise { exercise: string; sets: number; avg_hr: number | null; peak_hr: number | null; peak_share: number | null; effort: number | null; rpe: number | null; recovery_bpm: number | null; e1rm: number | null }
export interface Effort {
  linked: boolean; why?: string; text?: string; advice?: string[]; watch?: { name: string; start: string; end: string }; max_hr?: number; resolution_s?: number;
  avg_hr?: number | null; peak_hr?: number | null; kj?: number | null; zones_min?: number[]; exercises?: EffortExercise[];
  sets?: { exercise: string; set: number; type: string; weight: number | null; reps: number | null; at: string; avg_hr: number | null; peak_hr: number | null; recovery_bpm: number | null }[];
  timeline?: [string, number, number][];
}
export interface EntryLog { exercise: string; sets: SetLog[]; note?: string; group?: string | null }
export interface Session { id: string; title: string; started_at: string; ended_at?: string | null; routine_id?: string | null; day?: number | null; entries: EntryLog[]; note?: string; bodyweight?: number | null; gym?: string | null; deload?: boolean; review?: "" | "real" | "wrong";
  /** On the phone only (7.8): a saved workout reopened to correct it. Finishing re-saves it (same id) with its own times. */
  editing?: boolean }
export type Progression = "double" | "linear" | "percent";
export interface PlanExercise { exercise: string; sets: number; reps: string; rest_s: number; note?: string; group?: string | null; progression?: Progression; percents?: number[] }
/** `weekdays`: 0 = Monday … 6 = Sunday (6.94); empty: in turn. */
export interface RoutineDay { name: string; exercises: PlanExercise[]; weekdays?: number[] }
export interface WeekSchedule { today: number | null; rest: boolean; next: { day: number; date: string; weekday: string } | null; week: { weekday: string; day: number | null; name: string | null }[] }
export interface Routine { id: string; name: string; days: RoutineDay[]; note?: string; active: boolean }
export interface GymProfile { id: string; name: string; bar: number; plates: number[]; dumbbells: number[]; stack_step?: number | null }
export interface WarmupStep { percent: number; reps: number }
export interface GymSettings {
  unit: "kg"; bar: number; plates: number[]; increment: number; rest_s: number;
  gyms: GymProfile[]; current_gym: string; warmups: boolean; warmup_steps: WarmupStep[]; muscle_targets?: Record<string, number[]>;
  shortcut_start?: string; shortcut_finish?: string; learn_rest?: boolean;
}
export interface Suggest { weight: number | null; reps: number; why: string; push?: boolean; per_set?: number[]; training_max?: number; last_note?: string | null; watch_effort?: number }
export type Area = "shoulder" | "elbow" | "wrist" | "lower back" | "knee";
export const AREAS: Area[] = ["shoulder", "elbow", "wrist", "lower back", "knee"];
export interface Niggle { id: string; area: Area; note: string; started: string; healed?: string | null }
export interface Video { id: string; date: string; exercise: string; session?: string | null; set?: number | null; weight?: number | null; reps?: number | null; note: string; type: string }
export interface Backup { name: string; tag: string; saved_at: string; bytes: number; sessions: number | null }
export interface Fitness { weight: number; first: string; latest: string; times: number; first_peak: number; latest_peak: number; delta_bpm: number; verdict: "fitter" | "harder" | "same"; text: string;
  series: { date: string; peak_hr: number; effort: number | null }[] }
export interface HeatDay { date: string; volume: number; sets: number; muscles: string[] }
export interface Summary { id: string; title: string; date: string; started_at: string; minutes: number | null; sets: number; exercises: number; volume: number; names: string[];
  /** Imported, and too big to be one workout (7.0): left out of records and stats until you say it's real. */
  held?: boolean }
export interface Gym {
  settings: GymSettings; exercises: Exercise[]; routines: Routine[]; active: { routine: string; next_day: number; schedule?: WeekSchedule | null } | null;
  recent: Summary[]; week: { week_of: string; sessions: number; sets_by_muscle: Record<string, number>; volume: number; cardio_min?: number; cardio_km?: number; cardio_sessions?: number };
  streak_weeks: number; total_sessions: number; niggles?: Niggle[];
  held?: Summary[]; muscles?: MuscleWeek[]; deload?: Deload; readiness?: { score: number | null; band: string | null } | null;
}
export interface MuscleWeek { muscle: string; sets: number; target: [number, number]; status: "under" | "in range" | "over" }
export interface Deload { active: boolean; until: string | null; suggest: boolean; why: string[] }
export interface Watch { name: string; start: string; minutes: number | null; avg_hr: number | null; max_hr: number | null; kj: number | null }
export interface Strength { bodyweight: number | null; lifts: { exercise: string; name: string; best: number; date: string; this_year: number | null; last_year: number | null; ratio: number | null; level: string | null }[] }
export interface YearStats { sessions: number; hours: number; sets: number; volume: number }
export interface YearReview extends YearStats {
  year: number; previous: YearStats; months: { month: string; sessions: number; volume: number; records: number }[];
  muscles: { muscle: string; sets: number }[]; best: { exercise: string; name: string; e1rm: number; date: string }[];
}
export interface Plan { routine: string; day: number; title: string; gym?: string; deload?: boolean; readiness?: { score: number | null; band: string } | null; exercises: (PlanExercise & { name: string; kind: Kind; equipment?: string; last: SetLog[]; suggest: Suggest; warmups?: { weight: number; reps: number }[];
  niggle?: { area: string; swap: string | null; name?: string; why: string; from: string | null }; rest_learned?: { seconds: number; planned: number; why: string } })[] }
export interface GymRecord { exercise: string; name: string; kind: string; text: string }
export interface ExerciseDetail {
  exercise: Exercise;
  records: { heaviest?: { weight: number; reps: number | null; date: string }; e1rm?: { value: number; date: string }; rep_max?: Record<string, { weight: number; date: string }>;
    most_reps?: { reps: number; weight: number | null; date: string }; best_volume?: { volume: number; date: string } };
  series: { date: string; e1rm: number | null; best: number | null; volume: number; reps: number }[];
  history: { session: string; date: string; sets: SetLog[]; e1rm: number | null; volume: number }[];
  fitness?: Fitness | null; videos?: Video[];
}

export interface Duplicate { from: string; from_name: string; from_sets: number; into: string; into_name: string; into_sets: number; sure: boolean }
export interface CoachChange { area: string; title: string; why: string }
export interface Coach { date?: string; changes: CoachChange[]; looked_at?: string[]; enough: boolean; text: string }
export interface Morning {
  plan: { done: boolean; rest?: boolean; title: string; lifts?: { name: string; sets: number; reps: string; weight: number | null }[]; more?: number; note?: string | null; days_since?: number | null } | null;
  routine?: string; day?: number; gym?: string; shortcut?: string; readiness?: { score: number | null; band: string | null } | null;
}

export interface ImportPreview {
  sets: number; workouts: number; from: string | null; to: string | null; replacing: number; already_logged?: string[]; jefit?: boolean; removing?: number;
  exercises: { name: string; sets: number; match: string | null; match_name: string | null; how: "exact" | "close" | "guess" | "none"; new_muscle: string }[];
}
/** What the weights in an import file are in; SirisGym saves kilograms either way. */
export type ImportUnit = "auto" | "kg" | "lb";

export interface Measurement { id?: string; date: string; waist?: number | null; chest?: number | null; hips?: number | null; neck?: number | null;
  arm?: number | null; thigh?: number | null; calf?: number | null; note?: string }
export interface Photo { id: string; date: string; pose: "front" | "side" | "back" | "other"; note: string }
export interface Body { measurements: Measurement[]; photos: Photo[]; weight: { date: string; kg: number; trend: number }[] }
export type BuildGoal = "strength" | "muscle" | "general";
export type BuildEquipment = "gym" | "dumbbells" | "bodyweight";
export interface BuildRequest { text?: string; days?: number | null; goal?: BuildGoal | null; minutes?: number | null; equipment?: BuildEquipment | null; avoid?: string[] }
export interface Built { routine: Routine; chosen: { days: number; goal: BuildGoal; minutes: number; equipment: BuildEquipment; avoid: string[] }; read: Partial<BuildRequest>; note: string }

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
  plan: (routine: string, day?: number, gymId?: string) =>
    api<Plan>(`${G}/plan?routine=${encodeURIComponent(routine)}${day != null ? `&day=${day}` : ""}${gymId ? `&gym=${encodeURIComponent(gymId)}` : ""}`),
  warmups: (exercise: string, weight: number, gymId?: string) =>
    api<{ warmups: { weight: number; reps: number }[] }>(`${G}/warmups?exercise=${encodeURIComponent(exercise)}&weight=${weight}${gymId ? `&gym=${encodeURIComponent(gymId)}` : ""}`),
  heatmap: (days = 371) => api<{ days: HeatDay[] }>(`${G}/heatmap?days=${days}`),
  finish: (s: Session) => api<{ summary: Summary; records: GymRecord[] }>(`${G}/sessions`, json(s)),
  sessions: (month?: string) => api<{ sessions: Summary[] }>(`${G}/sessions${month ? `?month=${month}` : ""}`),
  session: (id: string) => api<Omit<Session, "entries"> & { summary: Summary; records: GymRecord[]; entries: (EntryLog & { name: string })[]; watch?: Watch | null }>(`${G}/sessions/${id}`),
  build: (b: BuildRequest) => api<Built>(`${G}/builder`, json(b)),
  body: () => api<Body>(`${G}/body`),
  addMeasurement: (m: Measurement) => api<Measurement>(`${G}/measurements`, json(m)),
  deleteMeasurement: (id: string) => api<{ deleted: string }>(`${G}/measurements/${id}`, { method: "DELETE" }),
  addPhoto: async (file: File, date: string, pose: Photo["pose"]) => {
    const body = new FormData();
    body.append("file", file);
    body.append("date", date);
    body.append("pose", pose);
    const r = await request(`${G}/photos`, { method: "POST", body });
    return (await r.json()) as Photo;
  },
  /** The photo as a blob URL (it needs the sign-in, so an <img src> can't fetch it itself). */
  photoUrl: async (id: string) => URL.createObjectURL(await (await request(`${G}/photos/${id}`)).blob()),
  deletePhoto: (id: string) => api<{ deleted: string }>(`${G}/photos/${id}`, { method: "DELETE" }),
  niggles: () => api<{ niggles: Niggle[]; areas: Area[] }>(`${G}/niggles`),
  addNiggle: (area: Area, note = "") => api<Niggle>(`${G}/niggles`, json({ area, note })),
  healNiggle: (id: string) => api<Niggle>(`${G}/niggles/${id}/healed`, { method: "POST" }),
  addVideo: async (file: File, v: { exercise: string; session?: string; set?: number; weight?: number | null; reps?: number | null; note?: string }) => {
    const body = new FormData();
    body.append("file", file);
    for (const [k, val] of Object.entries(v)) if (val != null && val !== "") body.append(k, String(val));
    const r = await request(`${G}/videos`, { method: "POST", body });
    return (await r.json()) as Video;
  },
  /** The video as a blob URL (it needs the sign-in, like photos). */
  videoUrl: async (id: string) => URL.createObjectURL(await (await request(`${G}/videos/${id}`)).blob()),
  deleteVideo: (id: string) => api<{ deleted: string }>(`${G}/videos/${id}`, { method: "DELETE" }),
  refreshEffort: () => api<{ waiting: number }>(`${G}/effort/refresh`, { method: "POST" }),
  backups: () => api<{ backups: Backup[] }>(`${G}/backups`),
  restore: (name: string) => api<{ restored: string; sessions: number; saved_current_as: string | null }>(`${G}/backups/restore`, json({ name })),
  /** Download every set as CSV, or everything as JSON. */
  download: async (kind: "csv" | "json") => {
    const blob = await (await request(`${G}/export.${kind}`)).blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `sirisgym-${new Date().toISOString().slice(0, 10)}.${kind}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  },
  rest: (seconds: number, next: string) => api<{ ringing_in: number }>(`${G}/rest`, json({ seconds, next })),
  stopRest: () => api<{ stopped: boolean }>(`${G}/rest`, { method: "DELETE" }),
  swap: (exercise: string, gymId?: string | null) =>
    api<{ options: { id: string; name: string; equipment: string; same_pattern: boolean; last: SetLog[]; weight: number | null }[] }>(
      `${G}/swap?exercise=${encodeURIComponent(exercise)}${gymId ? `&gym=${encodeURIComponent(gymId)}` : ""}`),
  protein: () => api<{ target_g: number | null; eaten_g: number | null; per_kg: number; bodyweight: number | null; training_day: boolean; left_g: number | null }>(`${G}/protein`),
  schedule: (dryRun: boolean, minutes = 60) =>
    api<{ slot: { start: string; end: string } | null; title?: string; detail?: string; added?: boolean }>(`${G}/schedule`, json({ minutes, dry_run: dryRun })),
  cleanup: (dryRun = false) => api<{ entries_removed: number; exercises_removed: number; names: string[]; sessions_kept: number }>(`${G}/cleanup?dry_run=${dryRun}`, { method: "POST" }),
  effort: (id: string) => api<Effort>(`${G}/sessions/${id}/effort`),
  review: (id: string, verdict: "" | "real" | "wrong") => api<{ id: string; review: string; left: number }>(`${G}/sessions/${id}/review`, json({ verdict })),
  duplicates: () => api<{ duplicates: Duplicate[] }>(`${G}/duplicates`),
  merge: (source: string, into: string) => api<{ sets_moved: number; workouts: number }>(`${G}/merge`, json({ source, into })),
  coach: () => api<Coach>(`${G}/coach`),
  morning: () => api<Morning>(`${G}/morning`),
  deload: (on: boolean, days = 7) => api<Deload>(`${G}/deload`, json({ on, days })),
  strength: () => api<Strength>(`${G}/strength`),
  year: (y?: number) => api<YearReview>(`${G}/year${y ? `?year=${y}` : ""}`),
  importPreview: (file: File, unit: ImportUnit) => importFile<{ preview: ImportPreview }>(file, unit),
  importCommit: (file: File, unit: ImportUnit, choices: Record<string, string>) =>
    importFile<{ imported: { workouts: number; sets: number; new_exercises: number; skipped_days?: string[]; removed?: number; tidied?: number } }>(file, unit, choices),
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

/** Run an iPhone Shortcut by name, then come back to `back` (6.92). Only on iPhone/iPad; elsewhere nothing happens. */
export const shortcuts = {
  /** `text` goes to the Shortcut as its input (7.61: "finished" or "discarded"), so one stop Shortcut can tell them apart. */
  url: (name: string, back: string, text?: string) =>
    `shortcuts://x-callback-url/run-shortcut?name=${encodeURIComponent(name)}${text ? `&input=text&text=${encodeURIComponent(text)}` : ""}`
    + `&x-success=${encodeURIComponent(back)}&x-cancel=${encodeURIComponent(back)}&x-error=${encodeURIComponent(back)}`,
  open: (url: string) => { window.location.href = url; },
  run(name: string | undefined, backPath: string, text?: string): boolean {
    if (!name?.trim() || !/iPhone|iPad|iPod/.test(navigator.userAgent)) return false;
    this.open(this.url(name.trim(), `${window.location.origin}${backPath}`, text));
    return true;
  },
};

/** A set changed (7.8): a new weight carries down to the sets after it that aren't ticked yet and were empty or
 * following it (same weight as it had), as in Strong or JEFIT, so typing 60 on set 1 fills sets 2 and 3. Warm-ups don't carry. */
export function changeSet(sets: SetLog[], si: number, patch: Partial<SetLog>): SetLog[] {
  const old = sets[si];
  const carry = "weight" in patch && patch.weight != null && old.type !== "warmup";
  return sets.map((x, j) => {
    if (j === si) return { ...x, ...patch };
    if (carry && j > si && !x.done && x.type === old.type && (x.weight == null || x.weight === old.weight)) return { ...x, weight: patch.weight };
    return x;
  });
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

const WORDS: Record<string, number> = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, eleven: 11, twelve: 12,
  thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18, nineteen: 19, twenty: 20, thirty: 30, forty: 40, fifty: 50,
  sixty: 60, seventy: 70, eighty: 80, ninety: 90, hundred: 100 };

/** A spoken set (6.9): "100 by 5", "100 kilos for 5", "5 reps at 82.5", "bodyweight 10", "60 x 8 RPE 8", optionally after the exercise's name. */
export function parseSpoken(text: string): { weight?: number | null; reps?: number; rpe?: number; name?: string } | null {
  let t = ` ${text.toLowerCase().replace(/[,!?]/g, " ")} `;
  t = t.replace(/\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)\b/g, (w) => String(WORDS[w]));
  t = t.replace(/\b(\d) 100\b/g, (_, d) => String(Number(d) * 100)).replace(/\b(\d00) (?:and )?(\d{1,2})\b/g, (_, h, n) => String(Number(h) + Number(n)))
    .replace(/\b([2-9]0) ([1-9])\b/g, (_, a, b) => String(Number(a) + Number(b)))
    .replace(/(\d)\s*point\s*(\d)/g, "$1.$2").replace(/(\d) and a half/g, "$1.5");
  const rpeM = t.match(/\brpe\s*(\d+(?:\.\d)?)/);
  const rpe = rpeM ? Number(rpeM[1]) : undefined;
  if (rpeM) t = t.replace(rpeM[0], " ");
  const unit = "(?:\\s*(?:kg|kilos?|kilograms?))?";
  let m = t.match(new RegExp(`(\\d+(?:\\.\\d+)?)${unit}\\s*(?:by|x|times|for|×)\\s*(\\d+)(?:\\s*reps?)?`));
  let out: { weight?: number | null; reps?: number } | null = m ? { weight: Number(m[1]), reps: Number(m[2]) } : null;
  if (!out && (m = t.match(new RegExp(`(\\d+)\\s*reps?\\s*(?:at|with|of)\\s*(\\d+(?:\\.\\d+)?)${unit}`)))) out = { weight: Number(m[2]), reps: Number(m[1]) };
  if (!out && (m = t.match(/(?:body ?weight|no weight)\s*(?:for\s*)?(\d+)/))) out = { weight: null, reps: Number(m[1]) };
  if (!out && (m = t.match(/(\d+)\s*reps?\b/))) out = { reps: Number(m[1]) };
  if (!out || !out.reps || out.reps > 100) return null;
  const name = t.slice(0, m!.index).replace(/\b(log|logged|did|set|just)\b/g, " ").trim();
  return { ...out, ...(rpe && rpe >= 5 && rpe <= 10 ? { rpe } : {}), ...(name.length > 2 ? { name } : {}) };
}
