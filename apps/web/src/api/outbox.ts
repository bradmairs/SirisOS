import { ApiError, api, json, setOfflineKeeper } from "./client";
import { patchResource } from "./resource";
import { bigStore, getItem, removeItem, setItem } from "./store";
import { brain } from "./hub";
import { tasks } from "./tasks";

/** Offline capture (6.3): a note or task saved while SirisOS can't be reached
 * waits on this device and goes as soon as it can (back online, the app
 * opened again, or brought to the front). Kept in localStorage, so it
 * survives closing the app; photos over about 1.5 MB aren't kept. */
export type Item = { kind: "task"; text: string; due?: string | null } | { kind: "capture"; body: Parameters<typeof brain.capture>[0] }
  /** 8.9: a task ticked off, and a receipt or letter uploaded, with no connection. */
  | { kind: "task_done"; task: import("./tasks").TaskItem }
  | { kind: "document"; name: string; type: string; data: string }
  | { kind: "gym"; session: import("./gym").Session }
  /** 7.7: a health log (water, mood, a symptom) made with no connection. */
  | { kind: "health_log"; log: { kind: string; amount?: number; text?: string } }
  /** 7.7: "Got it" or dismiss on an inbox item. Approvals are never queued:
   * by the time they'd send, things may have changed. */
  | { kind: "inbox"; id: string; action: "acknowledge" | "dismiss" }
  /** 11.4: any everyday edit made offline (api/client.ts QUEUEABLE), sent as it was. */
  | { kind: "request"; method: string; path: string; body: string | null; label: string }
  /** 11.4: a question for SirisAI asked offline: asked when back, the answer comes as a notification. */
  | { kind: "ask"; prompt: string; conversationId?: string | null };
export type Pending = Item & { at: string };
/** 11.4: what SirisOS said no to when it synced, kept for you to retry or let go. */
export type Failed = Pending & { why: string; failed_at: string };

const KEY = "sirisos.outbox";
const FAILED_KEY = "sirisos.outbox.failed";
// 11.4: in IndexedDB there's room for photos and receipts; localStorage (the fallback) holds about 5 MB in all.
const MAX_PHOTO = () => (bigStore() ? 12_000_000 : 1_500_000);
const MAX_DOCUMENT = () => (bigStore() ? 20_000_000 : 2_500_000);
const listeners = new Set<(n: number) => void>();

function read(): Pending[] {
  try {
    const raw = getItem(KEY);
    return raw ? (JSON.parse(raw) as Pending[]) : [];
  } catch {
    return [];
  }
}

function write(items: Pending[]): boolean {
  let ok = true;
  if (items.length) ok = setItem(KEY, JSON.stringify(items));
  else removeItem(KEY);
  listeners.forEach((fn) => fn(items.length));
  return ok;
}

/** What's waiting, oldest first (the sync bar's list). */
export function pending(): Pending[] {
  return read();
}

export function failed(): Failed[] {
  try {
    return JSON.parse(getItem(FAILED_KEY) ?? "[]") as Failed[];
  } catch {
    return [];
  }
}

function setFailed(items: Failed[]) {
  if (items.length) setItem(FAILED_KEY, JSON.stringify(items.slice(-50)));
  else removeItem(FAILED_KEY);
  listeners.forEach((fn) => fn(read().length));
}

/** Let a waiting or failed change go. */
export function drop(at: string): void {
  write(read().filter((p) => p.at !== at));
  setFailed(failed().filter((p) => p.at !== at));
}

/** Try a failed change again (it goes back on the end of the queue). */
export function retry(at: string): void {
  const f = failed().find((p) => p.at === at);
  if (!f) return;
  setFailed(failed().filter((p) => p.at !== at));
  const { why: _w, failed_at: _f, ...item } = f;
  write([...read(), item as Pending]);
  void flush();
}

/** A short description of a waiting change, for the list. */
export function describe(p: Pending): string {
  switch (p.kind) {
    case "task": return `New task: ${p.text}`;
    case "task_done": return `Done: ${p.task.title}`;
    case "capture": return p.body.text ? `Capture: ${p.body.text.slice(0, 60)}` : p.body.url ? `Link: ${p.body.url}` : "Photo capture";
    case "document": return `Upload: ${p.name}`;
    case "gym": return `Workout: ${p.session.title ?? "SirisGym"}`;
    case "health_log": return `Health log: ${p.log.kind}`;
    case "inbox": return `Inbox: ${p.action}`;
    case "request": return p.label;
    case "ask": return `Ask SirisAI: ${p.prompt.slice(0, 60)}`;
    default: return "A change";
  }
}

/** The connection dropped or the phone is offline, as opposed to SirisOS saying no. A 502, 503 or 504 (or Cloudflare's
 * 520-524) is the way in answering for SirisOS while it's down (8.6): that's unreachable too, not a no, so what's waiting
 * is kept rather than thrown away. */
export function unreachable(e: unknown): boolean {
  if (e instanceof ApiError && (e.status === 0 || [502, 503, 504].includes(e.status) || (e.status >= 520 && e.status <= 524))) return true;
  return typeof navigator !== "undefined" && navigator.onLine === false;
}

/** A file as base64, to keep it for later (8.9). */
export async function fileData(file: File): Promise<string> {
  const buf = new Uint8Array(await file.arrayBuffer());
  let out = "";
  for (let i = 0; i < buf.length; i += 0x8000) out += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  return btoa(out);
}

/** Keep it for later; false when it can't be kept (storage full, or a big photo). */
export function keep(item: Item): boolean {
  if (item.kind === "capture" && (item.body.image?.length ?? 0) > MAX_PHOTO()) return false;
  if (item.kind === "document" && item.data.length > MAX_DOCUMENT()) return false;
  return write([...read(), { ...item, at: new Date().toISOString() }]);
}

export function waiting(): number {
  return read().length;
}

export function onWaiting(fn: (n: number) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

let flushing: Promise<number> | null = null;
const syncedListeners = new Set<(n: number) => void>();
/** Told how many went each time a sync sends something ("Synced 7 changes"). */
export function onSynced(fn: (n: number) => void): () => void {
  syncedListeners.add(fn);
  return () => syncedListeners.delete(fn);
}

/** 11.4: keep both. A note edited offline that changed on the server meanwhile is saved as a copy beside it. */
async function sendRequest(next: Extract<Pending, { kind: "request" }>): Promise<void> {
  const init: RequestInit = { method: next.method, body: next.body ?? undefined, headers: { "X-Sirisos-Replay": "1", "X-Sirisos-Made-At": next.at } };
  try {
    await api(next.path, init);
  } catch (e) {
    if (e instanceof ApiError && e.status === 409 && next.path === "/api/v1/brain/edit" && next.body) {
      const b = JSON.parse(next.body) as { title: string; body: string };
      const day = next.at.slice(0, 10);
      await brain.capture({ title: `${b.title} (edited offline ${day})`, text: b.body });
      return;
    }
    throw e;
  }
}

/** Send what's waiting, oldest first; stops at the first one that can't get through. Returns how many went. */
export function flush(): Promise<number> {
  if (flushing) return flushing;
  flushing = (async () => {
    let sent = 0;
    for (;;) {
      const [next, ...rest] = read();
      if (!next) break;
      try {
        if (next.kind === "task") await tasks.add(next.due !== undefined ? { text: next.text, due: next.due } : { text: next.text });
        else if (next.kind === "task_done") await tasks.done(next.task);
        else if (next.kind === "document") {
          const { life } = await import("./life");
          const bytes = Uint8Array.from(atob(next.data), (c) => c.charCodeAt(0));
          await life.addDocument(new File([bytes], next.name, { type: next.type }));
        }
        else if (next.kind === "gym") await (await import("./gym")).gym.finish(next.session);
        else if (next.kind === "health_log") await api("/api/v1/health/log", json({ ...next.log, text: next.log.text ?? "" }));
        else if (next.kind === "inbox") {
          const { inbox } = await import("./hub");
          await (next.action === "dismiss" ? inbox.dismiss(next.id) : inbox.act(next.id, next.action));
        } else if (next.kind === "request") await sendRequest(next);
        else if (next.kind === "ask") await api("/api/v1/assistant/ask-later", { ...json({ prompt: next.prompt, conversation_id: next.conversationId ?? null, asked_at: next.at }), headers: { "X-Sirisos-Replay": "1" } });
        else {
          // 11.4: a line captured offline is filed where it belongs too (a spend, a dinner, a task), else it's a note for Siris.
          const text = next.body.text?.trim();
          if (text && !next.body.image && !next.body.url && !text.includes("\n")) {
            const { capture } = await import("./assist");
            let routed: Awaited<ReturnType<typeof capture.route>> | null = null;
            try {
              routed = await capture.route(text);
            } catch (e) {
              if (unreachable(e)) throw e;  // still no connection: wait
            }
            if (!routed?.handled || routed.error) await brain.capture(next.body);
          } else await brain.capture(next.body);
        }
      } catch (e) {
        if (unreachable(e)) break;
        // SirisOS said no to this one: don't block the rest behind it, and keep it for you to look at (11.4).
        setFailed([...failed(), { ...next, why: e instanceof Error ? e.message : "SirisOS said no.", failed_at: new Date().toISOString() }]);
        write(rest);
        continue;
      }
      write(rest);
      sent += 1;
    }
    if (sent) syncedListeners.forEach((fn) => fn(sent));
    return sent;
  })().finally(() => {
    flushing = null;
  });
  return flushing;
}

/** Flush when the connection comes back or the app comes to the front, and every minute while something's waiting
 * (8.6): with signal but SirisOS down, nothing else would say it's back. */
const queuedListeners = new Set<(label: string) => void>();
/** Told each time an edit is kept for later ("Saved on this phone"). */
export function onQueued(fn: (label: string) => void): () => void {
  queuedListeners.add(fn);
  return () => queuedListeners.delete(fn);
}

/** 11.4: what an edit kept offline changes on screen straight away, where SirisOS can tell. */
function applyLocally(method: string, path: string, body: string | null): void {
  try {
    const habit = /^\/api\/v1\/mind\/habits\/([^/]+)\/check$/.exec(path);
    if (habit && method === "POST" && body) {
      const id = decodeURIComponent(habit[1]);
      const { done } = JSON.parse(body) as { done: boolean };
      patchResource<{ habits: { id: string; today?: boolean; streak?: number }[] }>("mind:habits", (d) => ({
        ...d, habits: d.habits.map((h) => (h.id === id ? { ...h, today: done, streak: Math.max(0, (h.streak ?? 0) + (done ? 1 : -1)) } : h)),
      }));
    }
  } catch { /* shown when it syncs */ }
}

export function keepRequest(method: string, path: string, body: string | null, label: string): boolean {
  const ok = keep({ kind: "request", method, path, body, label });
  if (ok) {
    applyLocally(method, path, body);
    queuedListeners.forEach((fn) => fn(label));
  }
  return ok;
}

export function startOutbox(): void {
  if (typeof window === "undefined") return;
  setOfflineKeeper(keepRequest);
  window.setInterval(() => { if (waiting()) void flush(); }, 60_000);
  window.addEventListener("online", () => void flush());
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && waiting()) void flush();
  });
  if (waiting()) void flush();
}
