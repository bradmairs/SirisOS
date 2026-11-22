import { useCallback, useEffect, useSyncExternalStore } from "react";
import { bigStore, getItem, keys, removeItem, setItem } from "./store";

/**
 * A tiny shared data cache (stale-while-revalidate) for API reads.
 *
 * - Screens that read the same key share one request and one result, so the
 *   sidebar, home and engineering screens don't each fetch the app list.
 * - Revisiting a screen renders the last result instantly, then refreshes in
 *   the background, so navigation never flashes a skeleton twice.
 * - One poll timer per key (not per component), paused while the app is in
 *   the background and caught up when it returns.
 * - Keys read with `persist` keep their last good result on the device, so
 *   the next launch (or a launch with no signal) shows it at once, marked
 *   with when it was fetched, and refreshes behind it. Sign-out wipes them.
 */

interface Entry<T> {
  key: string;
  data: T | undefined;
  error: string | null;
  updatedAt: number;
  loading: boolean;
  inflight: Promise<T> | null;
  fetcher: (fresh: boolean) => Promise<T>;
  listeners: Set<() => void>;
  snapshot: Snapshot<T>;
  refreshMs: number;
  timer: number | null;
  persist: boolean;
}

export interface Snapshot<T> {
  data: T | undefined;
  error: string | null;
  loading: boolean;
  updatedAt: number;
}

const entries = new Map<string, Entry<unknown>>();

const PERSIST_PREFIX = "sirisos.cache.";
// 11.4: kept in IndexedDB (api/store.ts), so a screen's data can be big; localStorage (the fallback) keeps it smaller.
const PERSIST_MAX_CHARS = () => (bigStore() ? 5_000_000 : 500_000);

function readPersisted<T>(key: string): { data: T; updatedAt: number } | null {
  try {
    const raw = getItem(PERSIST_PREFIX + key);
    if (!raw) return null;
    const value = JSON.parse(raw);
    return value && typeof value.updatedAt === "number" ? value : null;
  } catch {
    return null;
  }
}

function writePersisted<T>(key: string, data: T, updatedAt: number) {
  try {
    const raw = JSON.stringify({ data, updatedAt });
    if (raw.length <= PERSIST_MAX_CHARS()) setItem(PERSIST_PREFIX + key, raw);
  } catch {
    /* full or blocked: the in-memory cache still works */
  }
}

function clearPersisted() {
  keys(PERSIST_PREFIX).forEach((k) => removeItem(k));
}

/** 11.4: a queued offline write answers {queued: true}; it isn't data, so a screen keeps what it shows. */
function isQueued(data: unknown): boolean {
  return !!data && typeof data === "object" && (data as { queued?: unknown }).queued === true && Object.keys(data as object).length <= 2;
}

function entry<T>(key: string, fetcher: (fresh: boolean) => Promise<T>, refreshMs: number, persist = false): Entry<T> {
  let e = entries.get(key) as Entry<T> | undefined;
  if (!e) {
    const saved = persist ? readPersisted<T>(key) : null;
    e = {
      key,
      data: saved?.data,
      error: null,
      updatedAt: saved?.updatedAt ?? 0,
      loading: false,
      inflight: null,
      fetcher,
      listeners: new Set(),
      snapshot: { data: saved?.data, error: null, loading: false, updatedAt: saved?.updatedAt ?? 0 },
      refreshMs,
      timer: null,
      persist,
    };
    entries.set(key, e as Entry<unknown>);
  }
  e.fetcher = fetcher;
  if (persist && !e.persist) e.persist = true;
  e.refreshMs = Math.min(e.refreshMs || refreshMs, refreshMs || e.refreshMs);
  return e;
}

function publish<T>(e: Entry<T>) {
  e.snapshot = { data: e.data, error: e.error, loading: e.loading, updatedAt: e.updatedAt };
  e.listeners.forEach((fn) => fn());
}

// Bumped by clearResources (sign-out): a request that finishes after it never writes into the cleared store.
let generation = 0;

function load<T>(e: Entry<T>, fresh = false): Promise<T> {
  if (e.inflight && !fresh) return e.inflight;
  const gen = generation;
  e.loading = true;
  publish(e);
  const run = e
    .fetcher(fresh)
    .then((data) => {
      e.data = data;
      e.error = null;
      e.updatedAt = Date.now();
      if (e.persist && gen === generation) writePersisted(e.key, data, e.updatedAt);
      return data;
    })
    .catch((err: unknown) => {
      e.error = err instanceof Error ? err.message : "Request failed.";
      throw err;
    })
    .finally(() => {
      if (e.inflight === run) e.inflight = null;
      e.loading = false;
      publish(e);
    });
  e.inflight = run;
  return run;
}

function visible() {
  return typeof document === "undefined" || document.visibilityState === "visible";
}

function startPolling<T>(e: Entry<T>) {
  if (e.timer !== null || !e.refreshMs) return;
  e.timer = window.setInterval(() => {
    if (visible()) load(e).catch(() => undefined);
  }, e.refreshMs);
}

function stopPolling<T>(e: Entry<T>) {
  if (e.timer !== null && e.listeners.size === 0) {
    window.clearInterval(e.timer);
    e.timer = null;
  }
}

if (typeof document !== "undefined") {
  // Back from the background: catch up on anything that went stale.
  document.addEventListener("visibilitychange", () => {
    if (!visible()) return;
    const now = Date.now();
    entries.forEach((e) => {
      if (e.listeners.size && e.refreshMs && now - e.updatedAt >= e.refreshMs) load(e).catch(() => undefined);
    });
  });
}

export interface ResourceOptions {
  /** Poll interval while mounted and visible; 0 = no polling. */
  refreshMs?: number;
  /** Re-fetch on mount if the cached value is older than this (default 15s). */
  staleMs?: number;
  /** Skip fetching entirely (e.g. no query yet). */
  enabled?: boolean;
  /** Keep the last good result on this device for the next launch and offline. On by default since 11.4. */
  persist?: boolean;
}

export function useResource<T>(key: string, fetcher: (fresh: boolean) => Promise<T>, options: ResourceOptions = {}) {
  const { refreshMs = 0, staleMs = 15_000, enabled = true, persist = true } = options;
  const e = entry(key, fetcher, refreshMs, persist);

  const subscribe = useCallback(
    (fn: () => void) => {
      e.listeners.add(fn);
      startPolling(e);
      return () => {
        e.listeners.delete(fn);
        stopPolling(e);
      };
    },
    [e],
  );
  const snapshot = useSyncExternalStore(subscribe, () => e.snapshot, () => e.snapshot);

  useEffect(() => {
    if (enabled && Date.now() - e.updatedAt > staleMs) load(e).catch(() => undefined);
  }, [e, enabled, staleMs]);

  const reload = useCallback((fresh = false) => load(e, fresh), [e]);
  /** Update the cached value locally (optimistic edits), notifying every reader. */
  const mutate = useCallback(
    (data: T) => {
      if (isQueued(data)) return;  // saved offline: keep showing what's there until it syncs
      e.data = data;
      e.updatedAt = Date.now();
      if (e.persist) writePersisted(e.key, data, e.updatedAt);
      publish(e);
    },
    [e],
  );
  return { ...snapshot, reload, mutate };
}

/** Warm a key without subscribing (e.g. on hover or idle). */
export function prefetch<T>(key: string, fetcher: (fresh: boolean) => Promise<T>, staleMs = 15_000) {
  const e = entry(key, fetcher, 0);
  if (Date.now() - e.updatedAt > staleMs && !e.inflight) load(e).catch(() => undefined);
}

/** Fetch a key again if anything has read it (e.g. Home's widgets after an edit elsewhere). */
export function refreshResource(key: string) {
  const e = entries.get(key);
  if (e) load(e, true).catch(() => undefined);
}

/** Forget everything (sign-out, tests). */
export function clearResources() {
  generation += 1;
  entries.forEach((e) => {
    if (e.timer !== null) window.clearInterval(e.timer);
  });
  entries.clear();
  clearPersisted();
}

/** When each persisted key was last fetched: the oldest one Home is showing. */
export function oldestUpdate(keys: string[]): number | null {
  const times = keys.map((k) => entries.get(k)?.updatedAt ?? 0).filter((t) => t > 0);
  return times.length ? Math.min(...times) : null;
}

/** 11.4: change a key's data on this device (an offline edit shown straight away), whether or not anything's reading it. */
export function patchResource<T>(key: string, fn: (data: T) => T): boolean {
  const e = entries.get(key) as Entry<T> | undefined;
  const base = e?.data ?? readPersisted<T>(key)?.data;
  if (base === undefined) return false;
  const next = fn(base);
  if (e) {
    e.data = next;
    publish(e);
  }
  writePersisted(key, next, e?.updatedAt || readPersisted<T>(key)?.updatedAt || Date.now());
  return true;
}

/** 11.4: the oldest data on screen right now, for "Offline · showing what it had at…". */
export function shownSince(): number | null {
  const times = [...entries.values()].filter((e) => e.listeners.size > 0 && e.updatedAt > 0).map((e) => e.updatedAt);
  return times.length ? Math.min(...times) : null;
}

/** 11.4: after Get ready for offline filled the store in the background, forget what's in memory so screens read it. */
export function forgetLoaded(): void {
  entries.forEach((e) => {
    if (e.listeners.size === 0) {
      if (e.timer !== null) window.clearInterval(e.timer);
      entries.delete(e.key);
    }
  });
}
