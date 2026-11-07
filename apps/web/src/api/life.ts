import { api, json } from "./client";

/** Life admin and reply speed from SirisAI 4.6 (SirisOS 7.3). */
export interface Due { date: string; what: string; amount: number | null }
export interface Doc {
  id: number; added_at: string; filename: string; title: string; kind: string; sender: string;
  summary: string; due: Due[]; note_title: string | null; text?: string; reminders?: number;
}
export interface Bill {
  id: number; kind: "renewal" | "trial_ending" | "price_rise" | "bill_due"; service: string; subject: string;
  amount: number | null; old_amount: number | null; currency: string; due_date: string | null; status: string; label: string;
}
export interface Trip {
  title: string; destination: string; start: string; end: string; nights: number; key: string;
  weather: { date: string; high_c: number | null; low_c: number | null; rain_chance_percent: number | null }[];
  packing: string[]; house: string[]; away_mode: boolean;
}
export interface Stage { p50_ms: number | null; p95_ms: number | null; count: number }
export interface Job { name: string; runs?: number; last_start?: string; last_seconds?: number; last_error?: string | null; running?: boolean; slow?: boolean }
export interface Speed {
  timings: { stages: Record<string, Stage>; recent: { at: string; path: string; stages: Record<string, number> }[] };
  jobs: Job[];
}

const L = "/api/v1/life";

export const life = {
  documents: (q = "") => api<Doc[]>(`${L}/documents${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  addDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<Doc>(`${L}/documents`, { method: "POST", body: form });
  },
  document: (id: number) => api<Doc>(`${L}/documents/${id}`),
  deleteDocument: (id: number) => api<{ deleted: number }>(`${L}/documents/${id}`, { method: "DELETE" }),
  bills: (all = false) => api<Bill[]>(`${L}/bills${all ? "?all=true" : ""}`),
  scanBills: () => api<{ looked_at?: number; added?: number; skipped?: string }>(`${L}/bills/scan`, { method: "POST" }),
  setBill: (id: number, status: "done" | "ignored" | "open") => api<Bill>(`${L}/bills/${id}/status`, json({ status })),
  travel: () => api<Trip[]>(`${L}/travel`),
  away: (on: boolean) => api<{ away_mode: string }>(`${L}/travel/away?on=${on}`, { method: "POST" }),
  speed: () => api<Speed>(`${L}/speed`),
};

/** Things you own and people (7.7, SirisAI 5.0). */
export interface Thing {
  id: number; name: string; brand: string; model: string; room: string; bought: string | null; price: number | null; shop: string;
  warranty_until: string | null; manual: string; notes: string; document_id: number | null; warranty_days_left?: number; under_warranty?: boolean;
}
export interface Person {
  id: number; name: string; relation: string; birthday: string | null; anniversary: string | null; notes: string; last_contact: string | null;
  keep_in_touch_days: number | null; next_birthday?: string; days_to_birthday?: number; next_anniversary?: string; days_to_anniversary?: number; turning?: number | null;
}

export const things = {
  list: (q = "") => api<Thing[]>(`${L}/things${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  add: (t: Partial<Thing> & { warranty_months?: number }) => api<Thing>(`${L}/things`, json(t)),
  update: (id: number, t: Partial<Thing>) => api<Thing>(`${L}/things/${id}`, { method: "PUT", body: JSON.stringify(t) }),
  remove: (id: number) => api<{ deleted: number }>(`${L}/things/${id}`, { method: "DELETE" }),
};

export const people = {
  list: () => api<Person[]>(`${L}/people`),
  add: (p: Partial<Person>) => api<Person>(`${L}/people`, json(p)),
  update: (id: number, p: Partial<Person>) => api<Person>(`${L}/people/${id}`, { method: "PUT", body: JSON.stringify(p) }),
  remove: (id: number) => api<{ deleted: number }>(`${L}/people/${id}`, { method: "DELETE" }),
  gifts: (id: number) => api<{ ideas: string[]; last_seen: { text: string; days_ago?: number } }>(`${L}/people/${id}/gifts`),
};
