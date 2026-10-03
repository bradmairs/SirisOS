import { useCallback, useEffect, useSyncExternalStore } from "react";

/**
 * A tiny shared data cache (stale-while-revalidate) for API reads.
 *
 * - Screens that read the same key share one request and one result, so the
 *   sidebar, home and engineering screens don't each fetch the app list.
 * - Revisiting a screen renders the last result instantly, then refreshes in
 *   the background, so navigation never flashes a skeleton twice.
 * - One poll timer per key (not per component), paused while the app is in
 *   the background and caught up when it returns.
 */

interface Entry<T> {
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
}

export interface Snapshot<T> {
  data: T | undefined;
  error: string | null;
  loading: boolean;
  updatedAt: number;
}

const entries = new Map<string, Entry<unknown>>();

function entry<T>(key: string, fetcher: (fresh: boolean) => Promise<T>, refreshMs: number): Entry<T> {
  let e = entries.get(key) as Entry<T> | undefined;
  if (!e) {
    e = {
      data: undefined,
      error: null,
      updatedAt: 0,
      loading: false,
      inflight: null,
      fetcher,
      listeners: new Set(),
      snapshot: { data: undefined, error: null, loading: false, updatedAt: 0 },
      refreshMs,
      timer: null,
    };
    entries.set(key, e as Entry<unknown>);
  }
  e.fetcher = fetcher;
  e.refreshMs = Math.min(e.refreshMs || refreshMs, refreshMs || e.refreshMs);
  return e;
}

function publish<T>(e: Entry<T>) {
  e.snapshot = { data: e.data, error: e.error, loading: e.loading, updatedAt: e.updatedAt };
  e.listeners.forEach((fn) => fn());
}

function load<T>(e: Entry<T>, fresh = false): Promise<T> {
  if (e.inflight && !fresh) return e.inflight;
  e.loading = true;
  publish(e);
  const run = e
    .fetcher(fresh)
    .then((data) => {
      e.data = data;
      e.error = null;
      e.updatedAt = Date.now();
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
}

export function useResource<T>(key: string, fetcher: (fresh: boolean) => Promise<T>, options: ResourceOptions = {}) {
  const { refreshMs = 0, staleMs = 15_000, enabled = true } = options;
  const e = entry(key, fetcher, refreshMs);

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
      e.data = data;
      e.updatedAt = Date.now();
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

/** Forget everything (sign-out, tests). */
export function clearResources() {
  entries.forEach((e) => {
    if (e.timer !== null) window.clearInterval(e.timer);
  });
  entries.clear();
}
