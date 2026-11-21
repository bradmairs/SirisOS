import { api, json } from "./client";

/** 10.4: the weekend, the garden, fuel on the way to Shepparton, bins, the bedroom, tonight's watching,
 * container updates, the internet's speed and catch-ups. */

const put = (body: unknown): RequestInit => ({ method: "PUT", body: JSON.stringify(body) });

export type RouteKind = "run" | "hike" | "ride" | "walk" | "other";
export interface WeekendRoute { id: string; name: string; kind: RouteKind; hours: number; km: number | null; link: string | null; notes: string }
export interface WeekendWindow { date: string; start: string; end: string; hours: number; low_c: number; high_c: number; rain_chance: number; conditions: string; score: number; route: WeekendRoute | null }
export interface Weekend { days: string[]; windows: WeekendWindow[]; routes: WeekendRoute[]; readiness: { score: number; band: string } | null; recover: boolean; note: string | null }

export interface Garden { on: boolean; protocol: string | null; last_watered: string | null; water?: boolean; why?: string; hot?: boolean; coming_mm?: number; past_mm?: number; high_c?: number | null; unavailable?: boolean }

export interface FuelStation { id: string; name: string; brand: string | null; address: string; lat: number; lon: number; price: number; updated: string | null; off_km: number; km_in: number; maps: string }
export interface FuelSettings { on: boolean; weekday: number; leave: string; fuel_type: string; first_km: number; off_route_km: number; destination: { name: string; lat: number; lon: number }; home: { lat: number; lon: number } | null }
export interface Fuel {
  settings: FuelSettings; configured: boolean; why?: string; attribution?: string; best?: FuelStation | null; options?: FuelStation[];
  average?: number | null; saving_cents?: number | null; route_km?: number; note?: string; for: string | null; error?: string;
}

export type BinKind = "rubbish" | "recycling" | "green" | "glass";
export interface Bin { kind: BinKind; every_weeks: number; first: string }
export interface Bins { bins: Bin[]; next: { date: string; kinds: BinKind[]; text: string } | null; show: boolean; when: "tonight" | "this morning" | null }

export interface Bedroom {
  temp_entity: string | null; humidity_entity: string | null; low: number; high: number; show: boolean;
  temp?: number | null; humidity?: number | null; advice?: string | null; bedtime?: string;
  best?: { low: number; high: number; sleep: number; other: number; nights: number } | null; nights?: number;
}

export interface WatchItem { title: string; type: string; show?: string | null; why?: string; minutes?: number | null }
export interface Tonight {
  available: boolean; minutes_to_bed: number | null; bedtime: string | null; picks: WatchItem[]; on_deck: WatchItem[]; new_unwatched: WatchItem[];
  episodes: { series: string | null; episode?: string | null; season?: number | null; number?: number | null; air_date: string | null }[]; movies: { title: string | null; release?: string | null; kind?: string | null }[]; plex: boolean; guest_mode?: boolean;
}

export interface ContainerUpdate { container: string; image?: string | null; current?: string | null; available?: string | null; notes?: string | null }
export interface Containers { available: boolean; checked_at?: string | null; updates: ContainerUpdate[]; up_to_date: string[]; skipped: Record<string, string>; running: boolean; message?: string }

export interface Internet {
  available: boolean; speeds: { at: string; down: number; up: number }[]; outages: { start: string; end: string; seconds: number }[];
  daily: { date: string; down: number; up: number; tests: number }[]; plan: { down: number | null; up: number | null }; slow: string[]; share_of_plan: number | null;
}

export interface Overdue { id: number; name: string; relation: string | null; days_since: number | null; gap: number; over_by: number }
export interface Catchups { available: boolean; overdue: Overdue[]; free: { date: string; part: "morning" | "afternoon" | "evening" }[]; keeping_up: number }

export const routines = {
  weekend: () => api<Weekend>("/api/v1/weekend"),
  setRoutes: (routes: Partial<WeekendRoute>[]) => api<Weekend>("/api/v1/weekend/routes", put({ routes })),
  garden: () => api<Garden>("/api/v1/garden"),
  setGarden: (body: { on?: boolean; protocol?: string | null }) => api<Garden>("/api/v1/garden", put(body)),
  watered: () => api<Garden>("/api/v1/garden/watered", { method: "POST" }),
  fuel: () => api<Fuel>("/api/v1/fuel"),
  setFuel: (body: Partial<Omit<FuelSettings, "destination">>) => api<Fuel>("/api/v1/fuel/settings", put(body)),
  bins: () => api<Bins>("/api/v1/bins"),
  setBins: (bins: Bin[]) => api<Bins>("/api/v1/bins", put({ bins })),
  bedroom: () => api<Bedroom>("/api/v1/bedroom"),
  setBedroom: (body: Partial<Pick<Bedroom, "temp_entity" | "humidity_entity" | "low" | "high">>) => api<Bedroom>("/api/v1/bedroom", put(body)),
  tonight: () => api<Tonight>("/api/v1/watch/tonight"),
  containers: () => api<Containers>("/api/v1/lab/containers"),
  checkContainers: () => api<Containers>("/api/v1/lab/containers/check", { method: "POST" }),
  updateContainers: (containers: string[]) => api<{ started: number; order: string[]; message: string }>("/api/v1/lab/containers/update", json({ containers })),
  internet: () => api<Internet>("/api/v1/lab/internet"),
  setPlan: (down: number | null, up: number | null) => api<Internet>("/api/v1/lab/internet/plan", put({ down, up })),
  catchups: () => api<Catchups>("/api/v1/catchups"),
  caughtUp: (id: number) => api<Catchups>(`/api/v1/catchups/${id}/done`, { method: "POST" }),
  setGap: (id: number, days: number | null) => api<Catchups>(`/api/v1/catchups/${id}`, put({ days })),
};
