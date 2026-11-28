import { api, request } from "./client";

/** SirisTrails (11.22): walks of an hour or more and every hike, with their GPS routes, from Apple Health. */
export interface Walk {
  id: string; kind: "walk" | "hike"; start: string; end: string | null; name: string; note: string;
  minutes: number | null; km: number | null; kcal: number | null; avg_hr: number | null; max_hr: number | null;
  moving_minutes: number | null; ascent_m: number | null; descent_m: number | null; highest_m: number | null; lowest_m: number | null;
  pace_min_per_km: number | null; start_point: [number, number]; line: [number, number][]; source: string;
  /** 12.1: from OpenStreetMap (places.py); name_auto is false once you've renamed it. */
  /** 12.2.3: the walk's own time zone, from where it was */
  tz?: string | null;
  /** 12.4: the weather it was walked in (Open-Meteo), and how many times you've walked this route */
  weather?: TrailWeather; repeats?: number | null;
  /** 12.5 */
  photos?: TrailPhoto[]; trimmed?: [number, number]; joined?: string[];
  place?: string | null; loop?: boolean; name_auto?: boolean; region?: string | null; country?: string | null; country_code?: string | null; landmarks?: { peak?: string; trail?: string; park?: string; locality?: string };
}
/** 12.5: where on the route it was taken (null when it couldn't be placed) */
export interface TrailPhoto { id: string; taken: string | null; at: [number, number] | null; km: number | null; w: number | null; h: number | null }
export interface TrailWeather { temp_c: number; temp_min_c: number; temp_max_c: number; feels_c: number | null; rain_mm: number | null;
  wind_kmh: number | null; gust_kmh: number | null; humidity: number | null; code: number | null; sky: string; icon: string }
/** 12.4: walks along the same route */
export interface RepeatRoute { id: string; name: string; count: number; km: number; latest: string;
  fastest: { id: string; minutes: number; start: string } | null;
  times: { id: string; start: string; minutes: number | null; pace: number | null }[] }
export interface Landmark { name: string; count: number; walks: string[]; first: string; last: string; place: string | null; country_code: string | null; highest_m: number | null }
export interface WalkTrip { id: string; name: string; place: string; country: string | null; country_code: string | null; from: string; to: string;
  walks: string[]; count: number; hikes: number; km: number; hours: number; ascent_m: number; travel?: { id: string; destination: string } }
export interface Split { km: number; length_km: number; minutes: number | null; pace_min_per_km: number | null; up_m: number; down_m: number }
export interface WalkDetail extends Walk {
  route: [number, number][];
  /** [km, metres (smoothed), lat, lon] */
  profile: [number, number, number, number][];
  splits: Split[];
  repeat: RepeatRoute | null;
  km_marks: [number, number, number][];
}
export interface TrailRecord { id: string; name: string; value: number; start: string; tz?: string | null }
export interface Trails {
  walks: Walk[]; count: number; hikes: number; km: number; hours: number; ascent_m: number;
  highest_m: number | null; longest_km: number | null; years: number[];
  /** 12.2 */
  avg_km: number | null; avg_minutes: number | null; avg_pace: number | null; countries: number; regions: number; places: number;
  where: { country: string; code: string | null; flag: string; walks: number; km: number; hours: number; regions: { region: string; walks: number; km: number; places: number }[] }[];
  records: { longest: TrailRecord | null; longest_time: TrailRecord | null; most_climbing: TrailRecord | null; highest: TrailRecord | null };
  by_year: { year: number; walks: number; km: number; hours: number }[];
  /** 12.4 */
  repeats: RepeatRoute[]; landmarks: { peaks: Landmark[]; parks: Landmark[]; trails: Landmark[] }; trips: WalkTrip[];
  weather_records: { hottest: TrailRecord | null; coldest: TrailRecord | null; wettest: TrailRecord | null; windiest: TrailRecord | null };
}
/** 12.6 */
export interface StreetsSuburb { locality: string; region: string | null; country: string | null; walks: number; slug: string; ready: boolean;
  streets?: number; walked?: number; km?: number; km_walked?: number; share?: number; fetched?: string }
export interface StreetsDetail { locality: string; region: string | null; boundary: [number, number][][]; streets: number; walked: number;
  km: number; km_walked: number; share: number; lines: { name: string; line: [number, number][]; walked: boolean }[] }
export interface WishHit { osm: string; name: string; kind: "track" | "peak" | "park" | "place"; where: string; lat: number; lon: number }
export interface Wish { id: string; osm: string; name: string; kind: WishHit["kind"]; where: string; center: [number, number]; lines: [number, number][][];
  area: [number, number][][]; km: number | null; ascent_m: number | null; highest_m: number | null; added: string;
  done: { walk: string; name: string; start: string } | null }
export interface TrailsHome {
  latest: Pick<Walk, "id" | "name" | "kind" | "start" | "tz" | "km" | "minutes" | "ascent_m" | "place" | "weather"> & { times: number | null; best: boolean };
  year: { year: number; walks: number; km: number; hours: number; ascent_m: number }; last_30_days: { walks: number; km: number };
  wishlist: { open: number; done: number };
}
export interface TrailsImport { running?: boolean; error?: string | null; at?: string; workouts?: number; added?: number; already_here?: number; no_route?: number }

const T = "/api/v1/trails";
export const trails = {
  list: (year?: number) => api<Trails>(`${T}${year ? `?year=${year}` : ""}`),
  get: (id: string) => api<WalkDetail>(`${T}/${id}`),
  change: (id: string, c: { name?: string; note?: string }) => api<Walk>(`${T}/${id}`, { method: "PATCH", body: JSON.stringify(c) }),
  remove: (id: string) => api<{ ok: boolean }>(`${T}/${id}`, { method: "DELETE" }),
  // 12.5
  gpx: async (id: string, hideHome: boolean) => (await request(`${T}/${id}/gpx${hideHome ? "?hide_home=true" : ""}`)).text(),
  trim: (id: string, from_km: number, to_km: number) => api<Walk>(`${T}/${id}/trim`, { method: "POST", body: JSON.stringify({ from_km, to_km }) }),
  untrim: (id: string) => api<Walk>(`${T}/${id}/trim`, { method: "DELETE" }),
  join: (id: string, other: string) => api<Walk>(`${T}/${id}/join`, { method: "POST", body: JSON.stringify({ other }) }),
  split: (id: string) => api<Walk>(`${T}/${id}/join`, { method: "DELETE" }),
  addPhoto: (id: string, p: { full: Blob; thumb: Blob; w: number; h: number; info: { taken: string | null; lat: number | null; lon: number | null } }) => {
    const form = new FormData();
    form.append("photo", p.full, "photo.jpg");
    form.append("thumb", p.thumb, "thumb.jpg");
    form.append("w", String(p.w)); form.append("h", String(p.h));
    if (p.info.taken) form.append("taken", p.info.taken);
    if (p.info.lat != null && p.info.lon != null) { form.append("lat", String(p.info.lat)); form.append("lon", String(p.info.lon)); }
    return api<TrailPhoto>(`${T}/${id}/photos`, { method: "POST", body: form });
  },
  /** A blob: URL (images need the sign-in header, which an <img> can't send). */
  photoUrl: async (id: string, photo: string, thumb: boolean) => URL.createObjectURL(await (await request(`${T}/${id}/photos/${photo}${thumb ? "?thumb=true" : ""}`)).blob()),
  removePhoto: (id: string, photo: string) => api<{ ok: boolean }>(`${T}/${id}/photos/${photo}`, { method: "DELETE" }),
  // 12.6
  home: () => api<TrailsHome | null>(`${T}/home`),
  streets: () => api<StreetsSuburb[]>(`${T}/streets`),
  street: (slug: string) => api<StreetsDetail>(`${T}/streets/${slug}`),
  wishlist: () => api<Wish[]>(`${T}/wishlist`),
  searchWishes: (q: string) => api<WishHit[]>(`${T}/wishlist/search?q=${encodeURIComponent(q)}`),
  addWish: (osm: string) => api<Wish>(`${T}/wishlist`, { method: "POST", body: JSON.stringify({ osm }) }),
  removeWish: (id: string) => api<{ ok: boolean }>(`${T}/wishlist/${id}`, { method: "DELETE" }),
  importStatus: () => api<TrailsImport>(`${T}/import`),
  uploadExport: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<{ started: boolean; bytes: number }>(`${T}/apple-export`, { method: "POST", body: form });
  },
};
