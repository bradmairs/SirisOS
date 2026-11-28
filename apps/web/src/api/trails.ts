import { api } from "./client";

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
  place?: string | null; loop?: boolean; name_auto?: boolean; region?: string | null; country?: string | null; country_code?: string | null; landmarks?: { peak?: string; trail?: string; park?: string; locality?: string };
}
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
export interface TrailsImport { running?: boolean; error?: string | null; at?: string; workouts?: number; added?: number; already_here?: number; no_route?: number }

const T = "/api/v1/trails";
export const trails = {
  list: (year?: number) => api<Trails>(`${T}${year ? `?year=${year}` : ""}`),
  get: (id: string) => api<WalkDetail>(`${T}/${id}`),
  change: (id: string, c: { name?: string; note?: string }) => api<Walk>(`${T}/${id}`, { method: "PATCH", body: JSON.stringify(c) }),
  remove: (id: string) => api<{ ok: boolean }>(`${T}/${id}`, { method: "DELETE" }),
  importStatus: () => api<TrailsImport>(`${T}/import`),
  uploadExport: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<{ started: boolean; bytes: number }>(`${T}/apple-export`, { method: "POST", body: form });
  },
};
