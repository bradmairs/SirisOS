import { useEffect, useState, useSyncExternalStore } from "react";
import { Undo2 } from "lucide-react";

/**
 * Undo instead of "Are you sure?" (11.15). An everyday delete happens on screen at once (`hide`), with an Undo banner
 * for a few seconds; only then is it sent (`run`). Undo puts it back (`restore`) and nothing is sent. Leaving the app
 * (the page hidden) sends what's waiting straight away, so nothing is lost by closing it. If sending fails, the item is
 * put back and the banner says so.
 *
 * Kept for: deleting a range of health data (no undo), discarding a whole workout, and settings.
 */
export interface Undoable { text: string; run: () => Promise<unknown> | unknown; hide?: () => void; restore?: () => void }

const WAIT_MS = 6000;
type Pending = Undoable & { id: number; timer: number };
let pending: Pending[] = [];
let failed: string | null = null;
let next = 1;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((fn) => fn());

async function send(p: Pending) {
  window.clearTimeout(p.timer);
  pending = pending.filter((x) => x.id !== p.id);
  notify();
  try {
    await p.run();
  } catch (e) {
    p.restore?.();
    failed = `Couldn't ${p.text.charAt(0).toLowerCase()}${p.text.slice(1)}: ${e instanceof Error ? e.message : "it failed"}. It's back.`;
    notify();
  }
}

/** Do it on screen now and send it in a few seconds, unless Undo is tapped. */
export function undoable(u: Undoable): void {
  u.hide?.();
  const p = { ...u, id: next++, timer: 0 } as Pending;
  p.timer = window.setTimeout(() => void send(p), WAIT_MS);
  pending = [...pending, p];
  failed = null;
  notify();
}

/** Send everything waiting now (the page is going away). */
export function flushUndoables(): void {
  for (const p of [...pending]) void send(p);
}

function undo(id: number) {
  const p = pending.find((x) => x.id === id);
  if (!p) return;
  window.clearTimeout(p.timer);
  pending = pending.filter((x) => x.id !== id);
  p.restore?.();
  notify();
}

function snapshot() { return pending.length ? pending[pending.length - 1] : null; }

/** The banner at the bottom of the screen: the latest change waiting, with Undo; mounted once in the app's shell. */
export function UndoBanner() {
  const latest = useSyncExternalStore((fn) => { listeners.add(fn); return () => listeners.delete(fn); }, snapshot, snapshot);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const onChange = () => setError(failed);
    listeners.add(onChange);
    const hidden = () => { if (document.visibilityState === "hidden") flushUndoables(); };
    document.addEventListener("visibilitychange", hidden);
    window.addEventListener("pagehide", flushUndoables);
    return () => { listeners.delete(onChange); document.removeEventListener("visibilitychange", hidden); window.removeEventListener("pagehide", flushUndoables); };
  }, []);
  useEffect(() => {
    if (!error) return undefined;
    const t = window.setTimeout(() => { failed = null; setError(null); }, 6000);
    return () => window.clearTimeout(t);
  }, [error]);
  if (!latest && !error) return null;
  return (
    <div className="undo-banner" role="status" aria-live="polite">
      {latest ? (
        <>
          <span>{latest.text}</span>
          <button type="button" className="undo-banner__btn" onClick={() => undo(latest.id)}><Undo2 size={15} aria-hidden="true" /> Undo</button>
        </>
      ) : <span className="tone-warning">{error}</span>}
    </div>
  );
}
