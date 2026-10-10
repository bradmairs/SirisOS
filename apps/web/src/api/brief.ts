import { api } from "./client";
import type { Tone } from "./types";

export interface BriefStatus {
  date: string;
  /** Inside the morning window and not dismissed today: open the brief by itself. */
  show: boolean;
  dismissed_today: boolean;
  from: string;
  until: string;
}

export interface BriefStory {
  title: string;
  url: string;
  source: string;
  published: string | null;
  topic: string;
  /** Interests from the Second Brain this story mentions. */
  matches: string[];
}

export interface Brief {
  date: string;
  weekday: string;
  generated_at: string;
  greeting: string;
  headline: string[];
  weather: {
    now: { temperature_c?: number; conditions?: string } | null;
    today: { high_c?: number; low_c?: number; conditions?: string; rain_chance_percent?: number } | null;
  };
  schedule: { title: string; time: string; start?: string | null; location?: string | null; calendar?: string | null }[];
  tasks: { title: string; detail?: string | null; tone: Tone; source: string }[];
  todo: string[];
  email: { unread: number; important: { from: string; subject: string }[] } | null;
  health: string[];
  home: string[];
  apps_attention: { name: string; state: string; detail: string }[];
  brain: { inbox: number; auto_linked: number; pending_links: number; unsure_links: number; highlights: string[] };
  career?: {
    cpd: { total: number; required: number; records: number; expiring_90_days: number };
    next_steps: { title: string; detail: string; kind: string }[];
    goals: { title: string; target_date: string | null }[];
  } | null;
  news: { topics: { topic: string; stories: BriefStory[] }[]; interests_from?: string; feeds_failed?: number; feeds_total?: number };
  /** SirisAI's attention counts (ADR 110); null from an older SirisAI. */
  attention?: { open: number; urgent: number } | null;
  /** SirisAI's guest mode: personal sections were left out. */
  guest_mode?: boolean;
  unavailable: string[];
  status: BriefStatus;
}

export const brief = {
  get: (fresh = false) => api<Brief>(`/api/v1/brief${fresh ? "?fresh=true" : ""}`),
  status: () => api<BriefStatus>("/api/v1/brief/status"),
  dismiss: () => api<BriefStatus>("/api/v1/brief/dismiss", { method: "POST" }),
};
