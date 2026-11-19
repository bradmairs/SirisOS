import { api } from "./client";

/** 10.2: trips: the weather there, packing, bills while away, the out-of-office. */
export interface TripDay { date: string; conditions: string; high_c: number | null; low_c: number | null; rain_chance: number | null; uv: number | null }
export interface Trip {
  id: string; destination: string; place: string | null; country: string; start: string; end: string; notes: string; ooo_done: boolean;
  packing: { item: string; done: boolean }[];
}
export interface TripView extends Trip {
  days_to_go: number; nights: number; away: boolean; weather: { days: TripDay[]; note: string | null };
  bills: { date: string; name: string; amount: number | null; kind: "charge" | "renewal" }[]; ooo_day: string; packed: number; to_pack: number;
}

const T = "/api/v1/travel";
export const travel = {
  list: () => api<{ next: TripView | null; upcoming: Trip[]; past: Trip[] }>(T),
  add: (t: { destination: string; start: string; end: string; notes?: string }) => api<TripView>(T, { method: "POST", body: JSON.stringify(t) }),
  current: () => api<{ trip: TripView | null }>(`${T}/current`),
  change: (id: string, c: { packing?: Trip["packing"]; ooo_done?: boolean; notes?: string }) => api<TripView>(`${T}/${id}`, { method: "PATCH", body: JSON.stringify(c) }),
  remove: (id: string) => api<{ removed: boolean }>(`${T}/${id}`, { method: "DELETE" }),
};
