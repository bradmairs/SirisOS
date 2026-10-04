export type AppState = "ok" | "degraded" | "down" | "unconfigured";
export type Tone = "neutral" | "good" | "warning" | "critical";
export type Category = "assistant" | "work" | "engineering" | "life";

export interface AppStatus {
  state: AppState;
  detail: string;
  latency_ms: number | null;
  version: string | null;
  checked_at: string;
}

export interface Metric {
  label: string;
  value: string;
  tone: Tone;
}

export interface WidgetItem {
  title: string;
  subtitle: string;
  url: string | null;
  tone: Tone;
}

export interface Widget {
  title: string;
  metrics: Metric[];
  items: WidgetItem[];
  empty: string;
  updated_at: string;
}

export type WidgetResult = Widget | { error: string };

export interface HubApp {
  id: string;
  name: string;
  category: Category;
  icon: string;
  description: string;
  launch_url: string | null;
  launch_only: boolean;
  configured: boolean;
  status: AppStatus;
  widget?: WidgetResult | null;
}

export interface PendingToolCall {
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolCallResult {
  name: string;
  arguments: Record<string, unknown>;
  result: unknown;
}

export interface ChatResponse {
  conversation_id: string;
  response: string | null;
  tool_call: ToolCallResult | null;
  confirmation_required: PendingToolCall | null;
  plan: ToolCallResult[] | null;
  used_planner: boolean;
}

export type ChatEvent =
  | { type: "status"; message: string }
  | { type: "thinking"; delta: string }
  | { type: "content"; delta: string }
  | { type: "tool_start"; name: string; arguments: Record<string, unknown> }
  | { type: "tool_end"; name: string; status: "ok" | "error" | "needs_confirmation" }
  | { type: "final"; response: ChatResponse }
  | { type: "error"; status: number; detail: string };

export interface ConversationSummary {
  conversation_id: string;
  started_with: string;
  last_at: string;
}

export interface BrainHit {
  title: string;
  path?: string;
  type?: string;
  tags?: string[];
  excerpts?: string[];
}

/** The vault engine's `brain.py insights`, via SirisAI's /siris/brain/insights. */
export interface BrainInsights {
  date: string;
  highlights: string[];
  summary: {
    notes: number;
    links: number;
    learned_by_siris: number;
    links_per_note: number;
    this_week: number;
    previous_week: number;
    streak_days: number;
    open_tasks: number;
    inbox: number;
  };
  activity: { date: string; notes: number }[];
  topics: { tag: string; notes: number; previous: number }[];
  hubs: { title: string; links: number }[];
  orphans: string[];
  stale_projects: { title: string; last_activity: string; days_idle: number }[];
  deadlines: { title: string; due: string; days_left: number }[];
  overdue_tasks: { task: string; note: string; due: string; days_late: number }[];
  inbox: { count: number; oldest: string | null };
  gaps: Record<string, number>;
  /** Only the unsure pairs: confident ones are linked automatically. */
  suggested_links: { a: string; b: string; score: number; confidence?: number | null; why: string }[];
  /** Links Siris made itself in the last two weeks that are still in place. */
  auto_linked?: { a: string; b: string; confidence: number | null; date: string }[];
  /** Confident pairs waiting for the next tidy (or "Link now"). */
  pending_auto_links?: number;
  link_thresholds?: {
    method: "embeddings" | "words";
    auto_min: number | null;
    suggest_min: number;
    basis: string;
    decisions: { linked: number; not_related: number; scored: number };
  };
}

export interface BrainNote {
  title: string;
  path: string;
  links: string[];
  backlinks: string[];
}

export function isWidget(w: WidgetResult | null | undefined): w is Widget {
  return !!w && !("error" in w);
}

/** SirisAI's /siris/hud/summary, as proxied at /api/v1/assistant/hud. Every block is optional. */
export interface Hud {
  time?: string;
  system?: {
    cpu_percent: number;
    cpu_count?: number;
    memory?: { total_gb: number; used_gb: number; percent_used: number };
    disk?: Record<string, { total_gb: number; used_gb: number; percent_used: number }>;
    temperatures_celsius?: Record<string, number>;
  } | null;
  weather?: {
    temperature_c: number;
    humidity_percent?: number | null;
    wind_speed_kmh?: number | null;
    precipitation_mm?: number | null;
    conditions: string;
  } | null;
  next_events?: { summary: string; start: string }[];
  parcels?: Record<string, unknown>[];
  autonomy?: { time: string; local_time: string; tool: string; what: string; why?: string; outcome: string }[];
  brain?: { title: string; action: string }[] | null;
}
