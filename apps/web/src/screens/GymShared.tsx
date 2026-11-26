import { useResource } from "../api/resource";
import { gym, newId, saveActive, savePlan, shortcuts, type Gym, type Plan, type Routine, type Session, type DayMode } from "../api/gym";

/** SirisGym's shared helpers (split out of Gym.tsx in 8.9): starting a workout, formatting, the overview. */

export const MUSCLES = ["chest", "back", "shoulders", "biceps", "triceps", "forearms", "abs", "quads", "hamstrings", "glutes", "calves", "full body", "cardio"];

export const EQUIPMENT = ["barbell", "dumbbell", "machine", "cable", "bodyweight", "kettlebell", "band", "smith", "ez bar", "trap bar", "other"];

export const fmtDay = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });

export const kg = (v: number | null | undefined, unit = "kg") => (v == null ? "–" : `${Number.isInteger(v) ? v : v.toFixed(1)} ${unit}`);

export function useGym() {
  return useResource<Gym>("gym", () => gym.get(), { staleMs: 30_000, persist: true });
}

/** The reps a set starts with: last time's at the same weight, or the bottom of the range. Never the top: ticking
 * through without changing it would log reps you didn't do, and the plan would add weight because of them. */
export function startingReps(e: Plan["exercises"][number], i: number, weight: number | null): number | null {
  if (e.kind !== "weight" && e.kind !== "bodyweight") return null;
  const before = e.last[i];
  if (before?.reps && (before.weight ?? null) === weight) return before.reps;
  return Number(e.reps.split("-")[0]) || null;
}

/** Start a workout: from a routine day (with last time, what to lift and warm-ups), or empty. */
export async function startWorkout(navigate: (to: string) => void, routine?: Routine, day?: number, gymId?: string, shortcut?: string, title = "Workout", mode: DayMode = "normal") {
  const now = new Date().toISOString();
  let s: Session = { id: newId(), title, started_at: now, entries: [], gym: gymId ?? null };
  if (routine) {
    const p = await gym.plan(routine.id, day, gymId, mode);
    s = { ...s, title: p.title, routine_id: routine.id, day: p.day, deload: !!p.deload, entries: p.exercises.map((e) => ({
      exercise: e.exercise,
      group: e.group ?? null,
      // 11.9: the boxes start empty, with last session's weight and reps (or the suggestion, for a first time) shown
      // faintly, so the sets still to do stand out and typing doesn't mean deleting what was there first.
      sets: [
        ...(e.warmups ?? []).map((w) => ({ weight: null, reps: null, hint: { weight: w.weight, reps: w.reps }, done: false, type: "warmup" as const })),
        ...Array.from({ length: e.sets }, (_, i) => {
          const suggested = e.suggest.per_set?.[i] ?? e.suggest.weight ?? null;
          const before = e.last[i];
          const weight = before?.weight ?? suggested ?? e.last.at(-1)?.weight ?? null;
          const reps = before?.reps ?? startingReps(e, i, weight);
          return { weight: null, reps: null, hint: { weight, reps }, done: false, type: "normal" as const };
        }),
      ],
    })) };
    savePlan(s.id, p);
  }
  saveActive(s);
  // A Shortcut first (e.g. start the Watch's strength workout), which comes back to the workout (6.92).
  navigate("/gym/workout");
  await runStartShortcut(shortcut);
}

/** 9.64: open the start Shortcut once the workout screen is up. A routine's start waited for its plan, so the Shortcut
 * opened after the screen had changed and iOS came back to SirisGym when it finished; an empty workout opened it in the
 * same instant as the screen change, and iOS left you in Shortcuts. Every start now waits the same short moment. */
export const SHORTCUT_DELAY_MS = 400;
export async function runStartShortcut(shortcut?: string): Promise<void> {
  if (!shortcut?.trim()) return;
  await new Promise((resolve) => window.setTimeout(resolve, SHORTCUT_DELAY_MS));
  shortcuts.run(shortcut, "/gym/workout");
}

/** What's on SirisGym, in a few lines for "Ask about this page" (7.5). */
export function gymSummary(g: Gym): string {
  const lines = [`${g.total_sessions} workouts logged, a ${g.streak_weeks}-week streak.`,
    `This week: ${g.week.sessions} workouts, ${Math.round(g.week.volume)} kg volume.`];
  if (g.readiness?.band) lines.push(`Readiness today: ${g.readiness.band}${g.readiness.score != null ? ` (${g.readiness.score})` : ""}.`);
  const under = (g.muscles ?? []).filter((m) => m.status === "under").map((m) => m.muscle);
  if (under.length) lines.push(`Under the weekly set target: ${under.join(", ")}.`);
  if (g.deload?.active) lines.push(`On a deload week until ${g.deload.until}.`);
  else if (g.deload?.suggest) lines.push(`A deload is suggested: ${g.deload.why.join("; ")}.`);
  if (g.recent[0]) lines.push(`Last workout: ${g.recent[0].title} on ${g.recent[0].date ?? ""}.`);
  return lines.join("\n");
}
