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
