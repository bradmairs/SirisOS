import { api } from "./client";

/** Which Home widgets show, and in what order, for one kind of device. */
export interface DeviceLayout {
  order: string[];
  hidden: string[];
}

export interface HomeLayout {
  phone: DeviceLayout;
  desktop: DeviceLayout;
  updated_at?: string | null;
}

export const EMPTY_LAYOUT: HomeLayout = { phone: { order: [], hidden: [] }, desktop: { order: [], hidden: [] } };

export const home = {
  layout: () => api<HomeLayout>("/api/v1/home/layout"),
  saveLayout: (layout: HomeLayout) => api<HomeLayout>("/api/v1/home/layout", { method: "PUT", body: JSON.stringify(layout) }),
};

/** Reorder `ids` by the saved order. The slots held by saved ids are refilled
 * in saved order; ids the layout doesn't mention (a new widget) stay where
 * they naturally fall. */
export function arrange(ids: string[], order: string[]): string[] {
  const rank = new Map(order.map((id, i) => [id, i]));
  const known = ids.filter((id) => rank.has(id)).sort((a, b) => rank.get(a)! - rank.get(b)!);
  let next = 0;
  return ids.map((id) => (rank.has(id) ? known[next++] : id));
}

/** Move `id` one place up or down within `ids`. */
export function move(ids: string[], id: string, by: -1 | 1): string[] {
  const i = ids.indexOf(id);
  const j = i + by;
  if (i < 0 || j < 0 || j >= ids.length) return ids;
  const out = [...ids];
  [out[i], out[j]] = [out[j], out[i]];
  return out;
}

export type DayPhase = "morning" | "work" | "weekend" | "evening" | "winddown" | "night";

/** One of today's or tomorrow's events, from SirisAI's calendar. */
export interface DayEvent { title: string; start: string; end?: string | null; all_day: boolean; location: string | null }

/** A day's forecast at home. */
export interface DayWeather { date: string; conditions?: string | null; high_c?: number | null; low_c?: number | null; rain_chance_percent?: number | null; precipitation_mm?: number | null }

export interface HomeContext {
  phase: DayPhase;
  /** The sections in the order they lead now (from the schedule); older servers leave it out. */
  sections?: string[];
  /** Widget ids this part of the day leaves out ("app:*" is every app's widget). */
  hidden?: string[];
  /** Minutes before an event with a place to suggest leaving. */
  leave_minutes?: number;
  /** When you got home (or left), from SirisAI's presence check. */
  home_since?: string | null;
  /** Today's and tomorrow's events (null in guest mode), and their weather. */
  events?: DayEvent[] | null;
  weather_today?: DayWeather | null;
  weather_tomorrow?: DayWeather | null;
  local_time: string;
  home: boolean | null;
  wrapped_up: boolean;
  top3: string[];
  tomorrow_top3: string[];
}

export const homeContext = () => api<HomeContext>("/api/v1/home/context");

/** Start times (HH:MM) through a day: `day` is work on a weekday, the daytime on a weekend. */
export interface DayTimes { morning: string; day: string; evening: string; winddown: string; night: string }

/** When each part of the day starts, and which sections lead in each (4.8). Shared by every device. */
export interface HomeSchedule {
  weekday: DayTimes;
  weekend: DayTimes;
  sections: Record<DayPhase, string[]>;
  hidden: Record<DayPhase, string[]>;
  leave_minutes: number;
}

export const schedule = {
  get: () => api<HomeSchedule>("/api/v1/home/schedule"),
  save: (s: HomeSchedule) => api<HomeSchedule>("/api/v1/home/schedule", { method: "PUT", body: JSON.stringify(s) }),
};

/** Which Home sections come first at each part of the day, until the server's
 *  schedule answers (the same defaults as app/home/schedule.py). Within a
 *  section, widgets keep the order you set in Customise Home. */
export const SECTION_ORDER: Record<DayPhase, string[]> = {
  morning: ["Now", "Today", "Home"],
  work: ["Today", "Now", "Home"],
  weekend: ["Home", "Today", "Now"],
  evening: ["Today", "Home", "Now"],
  winddown: ["Today", "Home", "Now"],
  night: ["Today", "Home", "Now"],
};

/** Every widget a part of the day can show or hide, as the schedule names them. */
export const DAY_WIDGETS: { id: string; label: string }[] = [
  { id: "clock", label: "Local time" }, { id: "weather", label: "Outside" }, { id: "server", label: "Home server" },
  { id: "app-health", label: "Siris apps" }, { id: "tasks", label: "Tasks" }, { id: "coming-up", label: "Coming up" },
  { id: "career", label: "Career" }, { id: "fitness", label: "Fitness" }, { id: "app:*", label: "App widgets (Engineering…)" },
  { id: "activity", label: "SirisAI activity" }, { id: "parcels", label: "Parcels" }, { id: "protocols", label: "Protocols" },
  { id: "cameras", label: "Cameras" }, { id: "car", label: "Car" }, { id: "energy", label: "Power" },
  { id: "brain", label: "Learned today" }, { id: "capture", label: "Quick capture" },
];

/** Until the server's schedule answers: the same defaults as app/home/schedule.py. */
const keep = (...ids: string[]) => DAY_WIDGETS.map((w) => w.id).filter((id) => !ids.includes(id));
export const DAY_HIDDEN: Record<DayPhase, string[]> = {
  morning: keep("clock", "weather", "tasks", "coming-up", "parcels", "protocols", "server", "app-health", "energy"),
  work: keep("clock", "weather", "tasks", "coming-up", "career", "app:*", "brain", "protocols", "server", "app-health"),
  weekend: keep("clock", "weather", "tasks", "coming-up", "fitness", "parcels", "car", "protocols", "cameras", "energy", "server", "app-health"),
  evening: keep("clock", "weather", "tasks", "coming-up", "fitness", "parcels", "car", "protocols", "cameras", "energy", "server", "app-health"),
  winddown: keep("brain", "capture"),
  night: keep("clock"),
};

/** Whether this part of the day leaves the widget out ("app:*" covers every app's widget). */
export function hiddenNow(id: string, hidden: string[]): boolean {
  return hidden.some((h) => h === id || (h.endsWith("*") && id.startsWith(h.slice(0, -1))));
}

/** The section order for now: the schedule's, with Home last while you're out (it's for when you're there). */
export function sectionOrder(phase: DayPhase, ctx: Pick<HomeContext, "sections" | "home"> | null): string[] {
  const order = ctx?.sections?.length ? ctx.sections : SECTION_ORDER[phase];
  return ctx?.home === false ? [...order.filter((s) => s !== "Home"), "Home"] : order;
}

const ADAPT_KEY = "sirisos.home.adaptive";

export function adaptive(): boolean {
  try {
    return localStorage.getItem(ADAPT_KEY) !== "off";
  } catch {
    return true;
  }
}

export function setAdaptive(on: boolean): void {
  try {
    localStorage.setItem(ADAPT_KEY, on ? "on" : "off");
  } catch {
    /* private mode: stays on for this visit */
  }
}

/** The part of the day from the device clock, until the server answers (the default schedule). */
export function localPhase(at = new Date()): DayPhase {
  const m = at.getHours() * 60 + at.getMinutes();
  const weekend = at.getDay() === 0 || at.getDay() === 6;
  const [day, evening] = weekend ? [10 * 60, 17 * 60] : [8 * 60 + 30, 16 * 60 + 30];
  if (m < 5 * 60 || m >= 23 * 60) return "night";
  if (m < day) return "morning";
  if (m < evening) return weekend ? "weekend" : "work";
  return m < 20 * 60 ? "evening" : "winddown";
}
