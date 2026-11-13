import { api, json } from "./client";
import type { TaskItem } from "./tasks";

export interface WeeklyReview {
  week_of: string;
  today: string;
  numbers: {
    tasks_done: number;
    notes: number | null;
    notes_before: number | null;
    cpd_hours: number;
    runs: number | null;
    run_km: number | null;
    exercise_minutes: number | null;
    meetings: number | null;
    wrapped_up: number;
  };
  done: string[];
  quiet: { title: string; days_idle: number }[];
  /** The weakest competency elements and what to do next (6.3). */
  /** The week's sleep report (6.4). */
  sleep?: import("./health").SleepWeek | null;
  /** 8.9: the year's goals behind the pace, and overdue tasks. */
  goals?: { through_year: number; behind: { title: string; percent: number | null }[]; on_track: number; done: { title: string; percent: number | null }[]; total: number } | null;
  overdue?: { id: string; title: string; due: string | null }[];
  gym?: { sessions: number; sets: number; volume: number; records: string[]; under: string[]; deload: boolean } | null;
  /** 9.4: mood and mindful minutes from Apple Health against last week, and each habit's ticks. */
  mind?: { mood: number | null; word: string | null; mood_before: number | null; mindful_minutes: number; mindful_before: number;
    habits: { name: string; done: number; of: number }[] } | null;
  chartership?: { counts: { solid: number; thin: number; none: number }; next: { id: string; title: string; strength: string; next: string }[] } | null;
  next_week: {
    busy_days: { date: string; meetings: number; clashes: string[] }[];
    meetings: number | null;
    tasks: TaskItem[];
    deadlines: { title: string; days_left: number; due?: string }[];
  };
  saved: { focus: string; saved_as: string | null; at: string } | null;
}

export const review = {
  get: () => api<WeeklyReview>("/api/v1/review"),
  save: (focus: string) => api<NonNullable<WeeklyReview["saved"]>>("/api/v1/review", json({ focus })),
};
