import { ApiError } from "./client";
import { brain } from "./hub";
import { tasks } from "./tasks";

/** Offline capture (6.3): a note or task saved while SirisOS can't be reached
 * waits on this device and goes as soon as it can (back online, the app
 * opened again, or brought to the front). Kept in localStorage, so it
 * survives closing the app; photos over about 1.5 MB aren't kept. */
export type Item = { kind: "task"; text: string } | { kind: "capture"; body: Parameters<typeof brain.capture>[0] };
export type Pending = Item & { at: string };

const KEY = "sirisos.outbox";
const MAX_PHOTO = 1_500_000;
const listeners = new Set<(n: number) => void>();

function read(): Pending[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Pending[]) : [];
  } catch {
    return [];
  }
}

function write(items: Pending[]): boolean {
  try {
    if (items.length) window.localStorage.setItem(KEY, JSON.stringify(items));
    else window.localStorage.removeItem(KEY);
    listeners.forEach((fn) => fn(items.length));
    return true;
  } catch {
    return false;
  }
}

/** The connection dropped or the phone is offline, as opposed to SirisOS saying no. */
export function unreachable(e: unknown): boolean {
  return (e instanceof ApiError && e.status === 0) || (typeof navigator !== "undefined" && navigator.onLine === false);
}

/** Keep it for later; false when it can't be kept (storage full, or a big photo). */
export function keep(item: Item): boolean {
  if (item.kind === "capture" && (item.body.image?.length ?? 0) > MAX_PHOTO) return false;
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

/** Send what's waiting, oldest first; stops at the first one that can't get through. Returns how many went. */
export function flush(): Promise<number> {
  if (flushing) return flushing;
  flushing = (async () => {
    let sent = 0;
    for (;;) {
      const [next, ...rest] = read();
      if (!next) break;
      try {
        if (next.kind === "task") await tasks.add({ text: next.text });
        else await brain.capture(next.body);
      } catch (e) {
        if (unreachable(e)) break;
        // SirisOS said no to this one (bad input): don't block the rest behind it.
      }
      write(rest);
      sent += 1;
    }
    return sent;
  })().finally(() => {
    flushing = null;
  });
  return flushing;
}

/** Flush when the connection comes back or the app comes to the front. */
export function startOutbox(): void {
  if (typeof window === "undefined") return;
  window.addEventListener("online", () => void flush());
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && waiting()) void flush();
  });
  if (waiting()) void flush();
}
