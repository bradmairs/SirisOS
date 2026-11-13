import { useSyncExternalStore } from "react";
import { api, json } from "./client";

/** Mental health (9.1): mood (Apple Health's State of Mind, or the 1-5 quick log) on one -1..1 scale, mindful minutes,
 * the calming tools and the journal. Clarity is fetched on its own, only when its card is opened. */
export interface MindDay { date: string; valence: number | null; word: string | null; entries?: number | null; logged?: number | null;
  mindful_minutes: number | null; here_minutes: number | null; sleep_hours?: number | null; exercise_minutes?: number | null }
export interface JournalEntry { id: string; at: string; kind: "gratitude" | "reframe" | "note"; text: string; [k: string]: string }
export interface Mind {
  available: boolean; days: MindDay[]; today: MindDay | null;
  week: { valence: number | null; word: string | null; before: number | null; mindful_minutes: number; mindful_before: number; mood_days: number };
  patterns: { key: string; text: string; with: number; without: number; days: number }[];
  journal_count: number; tools_minutes_week: number;
  /** 9.2: a passkey is set up, so the journal and Clarity open with Face ID. */
  locking: boolean;
}
export interface Habit { id: string; name: string; created: string; streak: number; best: number; today: boolean; rate: number; month: { date: string; done: boolean }[] }
export interface Clarity {
  started: string | null; streak: number; best: number; next: { days: number; left: number } | null; clear_last_30: number;
  month: { date: string; status: "clear" | "slip" | null }[]; checked_today: "clear" | "slip" | null;
  urges_week: number; rode_out_week: number; rode_out_all: number; triggers: { trigger: string; count: number }[];
  times: { part: string; count: number }[]; urges: { id: string; at: string; trigger: string; outcome: string; note: string }[];
  reasons: string[]; plan: string[];
  nudge: boolean; risky: { hour: number; count: number; nudge_at: string } | null;
}

/* -- the lock (9.2) -------------------------------------------------------------------------------------------------
 * Face ID (a passkey) opens the journal and Clarity for five minutes from the last use. The token lives only in memory
 * here, and is dropped when the app goes to the background, so it locks again whenever you leave. */
let unlock: { token: string; until: number } | null = null;
const listeners = new Set<() => void>();
const changed = () => listeners.forEach((fn) => fn());
export function unlocked(): boolean { return !!unlock && unlock.until > Date.now(); }
export function lockNow(): void {
  if (!unlock) return;
  const token = unlock.token;
  unlock = null;
  changed();
  api("/api/v1/mind/lock", { method: "POST", headers: { "X-Mind-Unlock": token } }).catch(() => {});
}
export function useUnlocked(): boolean {
  return useSyncExternalStore((fn) => { listeners.add(fn); return () => listeners.delete(fn); }, unlocked, () => false);
}
if (typeof document !== "undefined") document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") lockNow(); });

function b64(s: string): ArrayBuffer {
  const raw = atob((s + "=".repeat((4 - (s.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out.buffer;
}
function enc(buf: ArrayBuffer): string {
  let s = "";
  new Uint8Array(buf).forEach((x) => (s += String.fromCharCode(x)));
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Locked calls carry the token; a 423 means it ran out, so it locks. */
async function locked<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = { ...(init.headers as Record<string, string> | undefined), ...(unlock ? { "X-Mind-Unlock": unlock.token } : {}) };
  try {
    const out = await api<T>(path, { ...init, headers });
    if (unlock) unlock.until = Date.now() + 300_000;
    return out;
  } catch (e) {
    if ((e as { status?: number }).status === 423) { unlock = null; changed(); }
    throw e;
  }
}

const M = "/api/v1/mind";
export const mind = {
  /** Face ID, checked by SirisOS like a sign-in. */
  async unlock(): Promise<void> {
    const o = await api<{ challenge: string; rpId: string; userVerification: UserVerificationRequirement; allowCredentials: { type: "public-key"; id: string }[]; timeout: number }>(`${M}/unlock/options`, { method: "POST" });
    const cred = (await navigator.credentials.get({ publicKey: { challenge: b64(o.challenge), rpId: o.rpId, userVerification: o.userVerification,
      allowCredentials: o.allowCredentials.map((c) => ({ type: c.type, id: b64(c.id) })), timeout: o.timeout } })) as PublicKeyCredential | null;
    if (!cred) throw new Error("Face ID was cancelled.");
    const r = cred.response as AuthenticatorAssertionResponse;
    const got = await api<{ token: string; seconds: number }>(`${M}/unlock`, json({ challenge: o.challenge, id: cred.id,
      response: { clientDataJSON: enc(r.clientDataJSON), authenticatorData: enc(r.authenticatorData), signature: enc(r.signature), userHandle: r.userHandle ? enc(r.userHandle) : null } }));
    unlock = { token: got.token, until: Date.now() + got.seconds * 1000 };
    changed();
  },
  journalList: () => locked<{ journal: JournalEntry[] }>(`${M}/journal`),
  habits: () => api<{ habits: Habit[] }>(`${M}/habits`),
  addHabit: (name: string) => api<{ habits: Habit[] }>(`${M}/habits`, json({ name })),
  markHabit: (id: string, done: boolean, date?: string) => api<{ habits: Habit[] }>(`${M}/habits/${encodeURIComponent(id)}/check`, json({ done, date: date ?? null })),
  changeHabit: (id: string, change: { name?: string; archived?: boolean }) =>
    api<{ habits: Habit[] }>(`${M}/habits/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(change) }),
  nudge: (on: boolean) => locked<Clarity>(`${M}/clarity/nudge`, { method: "PUT", body: JSON.stringify({ on }) }),
  get: () => api<Mind>(M),
  journal: (kind: JournalEntry["kind"], text: string, extra: Record<string, string> = {}) => api<JournalEntry>(`${M}/journal`, json({ kind, text, extra })),
  unjournal: (id: string) => locked<{ deleted: string }>(`${M}/journal/${encodeURIComponent(id)}`, { method: "DELETE" }),
  session: (tool: "breathing" | "grounding" | "urge", seconds: number) => api<unknown>(`${M}/sessions`, json({ tool, seconds })),
  clarity: () => locked<Clarity>(`${M}/clarity`),
  start: (date?: string) => locked<Clarity>(`${M}/clarity/start`, json({ date: date ?? null })),
  check: (status: "clear" | "slip", note = "") => locked<Clarity>(`${M}/clarity/check`, json({ status, note })),
  urge: (trigger: string, outcome: "rode" | "slip", note = "") => locked<Clarity>(`${M}/clarity/urge`, json({ trigger, outcome, note })),
  plan: (reasons: string[], plan: string[]) => locked<Clarity>(`${M}/clarity/plan`, { method: "PUT", body: JSON.stringify({ reasons, plan }) }),
};
