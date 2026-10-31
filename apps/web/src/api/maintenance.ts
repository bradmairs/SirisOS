import { api, json, request } from "./client";

export type JobState = "unset" | "overdue" | "due" | "soon" | "ok";

export interface HomeJob {
  id: string;
  title: string;
  room: string;
  appliance: string | null;
  every_days: number | null;
  last_done: string | null;
  /** Due by use (6.2): a Home Assistant meter (kWh) or power sensor (hours running). */
  usage_entity?: string | null;
  usage_unit?: "h" | "kWh" | null;
  usage_every?: number | null;
  used?: number | null;
  used_share?: number | null;
  snoozed_until: string | null;
  notes: string;
  due_on: string | null;
  state: JobState;
  days: number | null;
}

export interface Appliance {
  id: string;
  name: string;
  room: string;
  device: string | null;
  make: string;
  model: string;
  bought_on: string | null;
  warranty_until: string | null;
  manual_url: string;
  manual: { filename: string; size: number } | null;
  notes: string;
  warranty_days: number | null;
}

export interface Maintenance {
  today: string;
  jobs: HomeJob[];
  appliances: Appliance[];
  summary: { overdue: number; due: number; soon: number; unset: number; rooms: string[]; warranties_ending: string[] };
}

export type NewJob = Pick<HomeJob, "title" | "room" | "every_days"> & Partial<Pick<HomeJob, "last_done" | "appliance" | "notes" | "usage_entity" | "usage_unit" | "usage_every">>;
export type ApplianceFields = Pick<Appliance, "name" | "room"> & Partial<Omit<Appliance, "id" | "manual" | "warranty_days">>;

const M = "/api/v1/maintenance";
const patch = (body: unknown) => ({ ...json(body), method: "PATCH" });

export const maintenance = {
  get: () => api<Maintenance>(M),
  addJob: (job: NewJob) => api<Maintenance>(`${M}/jobs`, json(job)),
  changeJob: (id: string, change: Partial<NewJob>) => api<Maintenance>(`${M}/jobs/${id}`, patch(change)),
  done: (id: string, on?: string) => api<Maintenance>(`${M}/jobs/${id}/done`, json(on ? { on } : {})),
  snooze: (id: string) => api<Maintenance>(`${M}/jobs/${id}/snooze`, { method: "POST" }),
  removeJob: (id: string) => api<Maintenance>(`${M}/jobs/${id}`, { method: "DELETE" }),
  addAppliance: (a: ApplianceFields) => api<Maintenance>(`${M}/appliances`, json(a)),
  changeAppliance: (id: string, change: Partial<ApplianceFields>) => api<Maintenance>(`${M}/appliances/${id}`, patch(change)),
  removeAppliance: (id: string) => api<Maintenance>(`${M}/appliances/${id}`, { method: "DELETE" }),
  uploadManual: async (id: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return (await (await request(`${M}/appliances/${id}/manual`, { method: "POST", body })).json()) as Maintenance;
  },
  async openManual(id: string) {
    const url = URL.createObjectURL(await (await request(`${M}/appliances/${id}/manual`)).blob());
    window.open(url, "_blank", "noopener");
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  },
};

/** "Overdue by 9 days", "Due today", "In 5 days", "When did you last do it?" */
export function dueText(j: HomeJob): string {
  const use = j.used != null && j.usage_every ? `${Math.round(j.used)} of ${j.usage_every} ${j.usage_unit === "h" ? "hours" : "kWh"} used` : null;
  if (use && (j.days == null || (j.used_share ?? 0) >= 85)) return use;
  if (j.state === "unset" || j.days == null) return "When did you last do it?";
  if (j.days < 0) return `Overdue by ${-j.days} day${j.days === -1 ? "" : "s"}`;
  if (j.days === 0) return "Due today";
  if (j.days === 1) return "Due tomorrow";
  return j.days < 60 ? `In ${j.days} days` : `In ${Math.round(j.days / 30)} months`;
}

export function everyText(days: number | null | undefined, j?: Pick<HomeJob, "usage_every" | "usage_unit">): string {
  const use = j?.usage_every ? `every ${j.usage_every} ${j.usage_unit === "h" ? "hours of use" : "kWh"}` : "";
  if (!days) return use ? use[0].toUpperCase() + use.slice(1) : "";
  return everyDays(days) + (use ? ` or ${use}` : "");
}

function everyDays(days: number): string {
  if (days % 365 === 0) return days === 365 ? "Every year" : `Every ${days / 365} years`;
  if (days % 30 === 0 && days >= 60) return `Every ${days / 30} months`;
  if (days === 30) return "Every month";
  if (days % 7 === 0) return days === 7 ? "Every week" : `Every ${days / 7} weeks`;
  return `Every ${days} days`;
}

export const EVERY_CHOICES: [number, string][] = [[7, "Every week"], [14, "Every 2 weeks"], [30, "Every month"], [90, "Every 3 months"],
  [180, "Every 6 months"], [365, "Every year"], [730, "Every 2 years"]];

/** How the house shows rooms with jobs that need doing. */
export function roomGlow(m: Maintenance | null | undefined): Record<string, { color: number; strength: number }> {
  const out: Record<string, { color: number; strength: number }> = {};
  for (const j of m?.jobs ?? []) {
    if (j.state === "overdue") out[j.room] = { color: 0xff7a45, strength: 1 };
    else if (j.state === "due" && !out[j.room]) out[j.room] = { color: 0xffb454, strength: 0.7 };
  }
  return out;
}
