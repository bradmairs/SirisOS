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

export type DayPhase = "morning" | "work" | "weekend" | "evening" | "night";

export interface HomeContext {
  phase: DayPhase;
  local_time: string;
  home: boolean | null;
  wrapped_up: boolean;
  top3: string[];
  tomorrow_top3: string[];
}

export const homeContext = () => api<HomeContext>("/api/v1/home/context");

/** Which Home sections come first at each part of the day (3.1). Within a
 *  section, widgets keep the order you set in Customise Home. */
export const SECTION_ORDER: Record<DayPhase, string[]> = {
  morning: ["Now", "Today", "Home"],
  work: ["Today", "Now", "Home"],
  weekend: ["Home", "Today", "Now"],
  evening: ["Home", "Today", "Now"],
  night: ["Today", "Home", "Now"],
};

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

/** The part of the day from the device clock, until the server answers (same rules as app/home/context.py). */
export function localPhase(at = new Date()): DayPhase {
  const h = at.getHours();
  if (h >= 5 && h < 10) return "morning";
  if (h >= 10 && h < 17) return at.getDay() === 0 || at.getDay() === 6 ? "weekend" : "work";
  if (h >= 17 && h < 23) return "evening";
  return "night";
}
