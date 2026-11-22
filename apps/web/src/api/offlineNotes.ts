import { ApiError } from "./client";
import { getItem, keys, removeItem, setItem } from "./store";
import type { BrainHit, BrainNote } from "./types";

/** 11.4: Siris notes to read offline. Every note opened is kept on the phone (the newest 300), and Get ready for
 * offline adds the most recent ones. With no connection, opening a note shows the kept copy and search looks through
 * the kept notes. */

const PREFIX = "sirisos.note.";
const MAX_NOTES = 300;

function offline(e: unknown): boolean {
  if (e instanceof ApiError && (e.status === 0 || [502, 503, 504].includes(e.status) || (e.status >= 520 && e.status <= 524))) return true;
  return typeof navigator !== "undefined" && navigator.onLine === false;
}

export function keepNote(note: BrainNote): void {
  if (!note?.title) return;
  setItem(PREFIX + note.title, JSON.stringify({ note, kept: Date.now() }));
  const all = keys(PREFIX);
  if (all.length > MAX_NOTES) {
    const dated = all.map((k) => { try { return [k, JSON.parse(getItem(k) ?? "{}").kept ?? 0] as [string, number]; } catch { return [k, 0] as [string, number]; } });
    dated.sort((a, b) => a[1] - b[1]).slice(0, all.length - MAX_NOTES).forEach(([k]) => removeItem(k));
  }
}

export function keptNote(title: string): (BrainNote & { offline_copy: number }) | null {
  try {
    const v = JSON.parse(getItem(PREFIX + title) ?? "null") as { note: BrainNote; kept: number } | null;
    return v ? { ...v.note, offline_copy: v.kept } : null;
  } catch {
    return null;
  }
}

export function keptCount(): number {
  return keys(PREFIX).length;
}

/** Look through the kept notes (title first, then the text). */
export function searchKept(q: string, limit = 12): BrainHit[] {
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const hits: { hit: BrainHit; score: number }[] = [];
  for (const k of keys(PREFIX)) {
    const n = keptNote(k.slice(PREFIX.length));
    if (!n) continue;
    const title = n.title.toLowerCase(), body = (n.body ?? "").toLowerCase();
    if (!words.every((w) => title.includes(w) || body.includes(w))) continue;
    const score = words.filter((w) => title.includes(w)).length * 10 + words.length;
    const at = body.indexOf(words[0]);
    hits.push({ hit: { title: n.title, path: n.path, tags: n.tags, excerpts: at >= 0 ? [(n.body ?? "").slice(Math.max(0, at - 60), at + 120)] : [] }, score });
  }
  return hits.sort((a, b) => b.score - a.score).slice(0, limit).map((h) => h.hit);
}

/** A note, kept on the way through; the kept copy when there's no connection. */
export async function noteWithCopy(fetch: () => Promise<BrainNote>, title: string): Promise<BrainNote> {
  try {
    const n = await fetch();
    keepNote(n);
    return n;
  } catch (e) {
    const copy = offline(e) ? keptNote(title) : null;
    if (copy) return copy;
    throw e;
  }
}

export async function searchWithCopy(fetch: () => Promise<BrainHit[]>, q: string, limit: number): Promise<BrainHit[]> {
  try {
    return await fetch();
  } catch (e) {
    if (offline(e)) return searchKept(q, limit);
    throw e;
  }
}
