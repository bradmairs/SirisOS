import { api, json } from "./client";

export type TaskGroup = "overdue" | "today" | "week" | "later" | "someday";
export type Repeat = "none" | "daily" | "weekdays" | "weekly" | "fortnightly" | "monthly";

export interface TaskItem {
  id: string;
  source: "sirisos" | "siris" | "reminder";
  title: string;
  detail: string | null;
  due: string | null;
  time: string | null;
  repeat: Repeat;
  group: TaskGroup;
  snoozed_until?: string | null;
  note?: string;
}

export interface TaskList {
  date: string;
  groups: Record<TaskGroup, TaskItem[]>;
  counts: Record<TaskGroup, number>;
  sources: { siris: boolean; reminders: boolean };
}

export interface NewTask {
  text?: string;
  title?: string;
  due?: string | null;
  time?: string | null;
  repeat?: Repeat;
  notes?: string;
}

export const tasks = {
  list: () => api<TaskList>("/api/v1/tasks"),
  add: (task: NewTask) => api<{ id: string; title: string; due: string | null; time: string | null; repeat: Repeat }>("/api/v1/tasks", json(task)),
  done: (task: TaskItem) => api<{ id: string; action: string; next_due?: string }>(`/api/v1/tasks/${encodeURIComponent(task.id)}/done`,
    json(task.source === "siris" ? { note: task.note ?? task.detail, title: task.title } : {})),
  snooze: (id: string, until: string) => api<{ id: string; snoozed_until: string }>(`/api/v1/tasks/${encodeURIComponent(id)}/snooze`, json({ until })),
  update: (id: string, changes: Partial<NewTask>) => api(`/api/v1/tasks/${encodeURIComponent(id)}`, { ...json(changes), method: "PATCH" }),
  remove: (id: string) => api(`/api/v1/tasks/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

/** "remind me to…" (or "todo:") in quick capture becomes a task, not a note. */
export const isTaskText = (text: string) => /^\s*(remind me( to)?|todo:?|to do:?|task:)\s+/i.test(text);

export const GROUP_LABEL: Record<TaskGroup, string> = { overdue: "Overdue", today: "Today", week: "This week", later: "Later", someday: "Someday" };

export function dueLabel(t: Pick<TaskItem, "due" | "time" | "group">, today = new Date()): string {
  if (!t.due) return "";
  const d = new Date(`${t.due}T00:00:00`);
  const days = Math.round((d.getTime() - new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()) / 86_400_000);
  const day = days === 0 ? "Today" : days === 1 ? "Tomorrow" : days === -1 ? "Yesterday" : days < 0 ? `${-days} days late`
    : days < 7 ? d.toLocaleDateString(undefined, { weekday: "long" }) : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  return t.time ? `${day} · ${t.time}` : day;
}
