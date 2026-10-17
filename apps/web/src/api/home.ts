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
