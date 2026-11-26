import { forgetLoaded } from "./resource";
import { getItem, reloadStore, setItem } from "./store";
import { keepNote, keptCount } from "./offlineNotes";

/**
 * Get ready for offline (11.4). One tap (or by itself the evening before a flight):
 *
 * 1. every section opens once, out of sight, in a frame of this app: its code is kept by the service worker and its
 *    data in the device store, exactly as a real visit would;
 * 2. the 30 most recently updated Siris notes are kept to read;
 * 3. it says what's ready: "Ready: 34 screens, 61 notes, data from 9:42pm".
 */

export const SCREENS = [
  "/", "/brief", "/inbox", "/tasks", "/projects", "/gym", "/gym?view=routines", "/gym?view=history", "/gym?view=progress",
  "/wrapup", "/review", "/year", "/health", "/health?view=sleep", "/health?view=mind", "/health?view=habits", "/fitness",
  "/budget", "/week", "/meals", "/house", "/life", "/travel", "/things", "/work", "/engineering", "/career", "/brain",
  "/links", "/status", "/homelab", "/handbook", "/sections", "/assistant",
];
const READY_KEY = "sirisos.offline.ready";
const WAIT_MS = 2600;

export interface Ready { at: number; screens: number; notes: number; failed: string[] }

export function lastReady(): Ready | null {
  try {
    return JSON.parse(getItem(READY_KEY) ?? "null") as Ready | null;
  } catch {
    return null;
  }
}

/** Is this the hidden frame Get ready uses? Then heartbeats, syncing and summaries stay with the real app. */
export function inPrepFrame(): boolean {
  try {
    return window.self !== window.top && new URLSearchParams(window.location.search).has("offline-prep");
  } catch {
    return false;
  }
}

let running: Promise<Ready> | null = null;

export function prepare(onProgress?: (done: number, total: number, what: string) => void): Promise<Ready> {
  if (running) return running;
  running = (async () => {
    const failed: string[] = [];
    const total = SCREENS.length + 1;
    const frame = document.createElement("iframe");
    frame.setAttribute("aria-hidden", "true");
    frame.tabIndex = -1;
    frame.style.cssText = "position:fixed;left:-10000px;top:0;width:390px;height:844px;border:0;opacity:0;pointer-events:none";
    document.body.appendChild(frame);
    try {
      for (let i = 0; i < SCREENS.length; i += 1) {
        const path = SCREENS[i];
        onProgress?.(i, total, path);
        const sep = path.includes("?") ? "&" : "?";
        const loaded = new Promise<void>((resolve) => { frame.onload = () => resolve(); });
        frame.src = `${path}${sep}offline-prep=1`;
        await Promise.race([loaded, new Promise((r) => setTimeout(r, 8000))]);
        await new Promise((r) => setTimeout(r, WAIT_MS));  // let the screen fetch its data
      }
    } catch {
      failed.push("screens");
    } finally {
      frame.remove();
    }
    onProgress?.(SCREENS.length, total, "Siris notes");
    try {
      const { brain } = await import("./hub");
      const recent = await brain.recent(30);
      for (const n of recent ?? []) {
        try { keepNote(await brain.note(n.title)); } catch { /* skip that one */ }
      }
    } catch {
      failed.push("notes");
    }
    await reloadStore();
    forgetLoaded();
    const ready: Ready = { at: Date.now(), screens: SCREENS.length, notes: keptCount(), failed };
    setItem(READY_KEY, JSON.stringify(ready));
    onProgress?.(total, total, "done");
    return ready;
  })().finally(() => { running = null; });
  return running;
}

/** The evening before a flight (a trip starting today or tomorrow, or a flight in the calendar within a day), and not
 * already ready in the last 12 hours: get ready by itself. */
export async function flightSoon(): Promise<boolean> {
  const last = lastReady();
  if (last && Date.now() - last.at < 12 * 3600_000) return false;
  try {
    const { travel } = await import("./travel");
    const t = await travel.list();
    if (t?.next && typeof t.next.days_to_go === "number" && t.next.days_to_go <= 1 && t.next.days_to_go >= 0) return true;
  } catch { /* no trips */ }
  try {
    const { assistant } = await import("./hub");
    const hud = await assistant.hud();
    const soon = Date.now() + 24 * 3600_000;
    return (hud?.next_events ?? []).some((e: { summary?: string; start?: string }) =>
      /\bflight\b|\b(QF|VA|JQ|NZ|EK|SQ|QR|ZL)\s?\d{2,4}\b/i.test(e.summary ?? "") && !!e.start && new Date(e.start).getTime() < soon);
  } catch {
    return false;
  }
}
