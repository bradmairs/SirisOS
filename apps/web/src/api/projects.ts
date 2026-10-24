import { api, json } from "./client";
import type { TaskItem } from "./tasks";
import type { WeekEvent } from "./week";

export interface ProjectSummary {
  title: string;
  status: string;
  aliases: string[];
  path: string | null;
  due: string | null;
  days_left: number | null;
  days_idle: number | null;
  open_tasks: number;
}

export interface ProjectPage extends Omit<ProjectSummary, "due" | "days_left" | "open_tasks"> {
  names: string[];
  about: string;
  areas: string[];
  source: string | null;
  updated: string | null;
  links: string[];
  backlinks: string[];
  deadline: { title: string; due: string; days_left: number } | null;
  tasks: TaskItem[];
  meetings: { upcoming: WeekEvent[]; recent: WeekEvent[] };
  guest_mode: boolean;
  unavailable: string[];
}

const P = "/api/v1/siris-projects";

export const projects = {
  list: () => api<{ projects: ProjectSummary[]; available: boolean }>(P),
  get: (title: string) => api<ProjectPage>(`${P}/${encodeURIComponent(title)}`),
  finish: (title: string) => api<{ action: string }>(`${P}/${encodeURIComponent(title)}/done`, { method: "POST" }),
  addTask: (title: string, text: string) => api<{ id: string; title: string }>(`${P}/${encodeURIComponent(title)}/tasks`, json({ text })),
};

export const FINISHED = ["done", "finished", "archived", "complete", "completed"];

export function dueWords(daysLeft: number | null): string | null {
  if (daysLeft == null) return null;
  if (daysLeft === 0) return "Due today";
  if (daysLeft === 1) return "Due tomorrow";
  return daysLeft > 0 ? `Due in ${daysLeft} days` : `${-daysLeft} day${daysLeft === -1 ? "" : "s"} overdue`;
}
