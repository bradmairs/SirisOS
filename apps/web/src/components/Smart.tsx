import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Bell, X } from "lucide-react";
import { api, json } from "../api/client";
import { deviceId, deviceLabel } from "../api/push";

/** 10.6: smarter notifications, the app's side.
 * - `useSeen(key)`: a card reports the notification it stands for once it's been on screen for two seconds, so
 *   SirisOS doesn't send it (or drops it from the roundup).
 * - `<AppPresence />`: while SirisOS is on screen it tells the server every minute (with this device's push address
 *   and any focus block running), so notifications come here as a banner instead of buzzing a phone. */

const SHOWN_MS = 2000;
const BEAT_MS = 60_000;
const BANNER_MS = 10_000;
let queue = new Set<string>();
let timer: ReturnType<typeof setTimeout> | null = null;
const sent = new Set<string>();

export function markSeen(keys: (string | null | undefined)[]) {
  for (const k of keys) if (k && !sent.has(k)) queue.add(k);
  if (!queue.size || timer) return;
  timer = setTimeout(() => {
    const keys = [...queue].slice(0, 50);
    queue = new Set([...queue].slice(50));
    timer = null;
    keys.forEach((k) => sent.add(k));
    api("/api/v1/push/seen", json({ keys })).catch(() => keys.forEach((k) => sent.delete(k)));
  }, 400);
}

/** Attach the returned ref to the card. `key` null: nothing to report. */
export function useSeen<T extends Element = HTMLElement>(key: string | null | undefined) {
  const [el, setEl] = useState<T | null>(null);
  useEffect(() => {
    if (!key || !el || sent.has(key)) return;
    let shown: ReturnType<typeof setTimeout> | null = null;
    const stop = () => { if (shown) { clearTimeout(shown); shown = null; } };
    if (typeof IntersectionObserver === "undefined") {
      shown = setTimeout(() => document.visibilityState !== "hidden" && markSeen([key]), SHOWN_MS);
      return stop;
    }
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && document.visibilityState !== "hidden") {
        if (!shown) shown = setTimeout(() => markSeen([key]), SHOWN_MS);
      } else stop();
    }, { threshold: 0.5 });
    io.observe(el);
    return () => { io.disconnect(); stop(); };
  }, [key, el]);
  return setEl as (node: T | null) => void;
}

/** Put inside a card (its header): the card's notification counts as seen once it's been on screen. */
export function SeenMark({ k }: { k: string | null | undefined }) {
  const ref = useSeen<HTMLSpanElement>(k);
  return <span ref={ref} aria-hidden="true" style={{ display: "inline-block", width: 1, height: 1 }} />;
}

/** A whole screen counts as seen after two seconds on it (the brief, the wrap-up, the weekly review). */
export function useSeenPage(key: string | null | undefined) {
  useEffect(() => {
    if (!key || sent.has(key)) return;
    const t = setTimeout(() => document.visibilityState !== "hidden" && markSeen([key]), SHOWN_MS);
    return () => clearTimeout(t);
  }, [key]);
}

export const today = () => new Date().toLocaleDateString("en-CA");

interface Banner { key: string; title: string; body: string; url: string; at: string }

function focusUntil(): string | null {
  try {
    const s = JSON.parse(window.localStorage.getItem("sirisos.work.focus") ?? "null") as { mode?: string; ends?: number | null } | null;
    return s && s.mode === "focus" && s.ends && s.ends > Date.now() ? new Date(s.ends).toISOString() : null;
  } catch { return null; }
}

function endpoint(): string | null {
  try { return window.localStorage.getItem("sirisos.push.endpoint"); } catch { return null; }
}

/** The heartbeat, and the banners for notifications that came while you were here. */
export function AppPresence() {
  const [banners, setBanners] = useState<Banner[]>([]);
  const beat = useCallback(async () => {
    const device = deviceId();
    if (document.visibilityState === "hidden" || device.length < 4) return;
    try {
      const r = await api<{ inapp: Banner[] }>("/api/v1/push/active", json({ device, endpoint: endpoint(), label: deviceLabel(), focus_until: focusUntil() }));
      if (Array.isArray(r?.inapp)) setBanners(r.inapp.slice(-3));
    } catch { /* offline or signed out: try next time */ }
  }, []);
  const last = useRef(0);
  useEffect(() => {
    const go = () => { if (Date.now() - last.current > 5_000) { last.current = Date.now(); void beat(); } };
    go();
    const t = setInterval(go, BEAT_MS);
    const vis = () => document.visibilityState === "visible" && go();
    document.addEventListener("visibilitychange", vis);
    return () => { clearInterval(t); document.removeEventListener("visibilitychange", vis); };
  }, [beat]);
  // Like a notification banner: it goes by itself after ten seconds (and counts as seen: it was on screen).
  useEffect(() => {
    if (!banners.length) return;
    const t = setTimeout(() => { markSeen(banners.map((b) => b.key)); setBanners([]); }, BANNER_MS);
    return () => clearTimeout(t);
  }, [banners]);
  if (!banners.length) return null;
  const done = (b: Banner) => { markSeen([b.key]); setBanners((xs) => xs.filter((x) => x.key !== b.key)); };
  return (
    <div className="inapp" role="region" aria-label="While you were here">
      {banners.map((b) => (
        <div key={b.key} className="inapp__banner" role="status">
          <Bell size={16} aria-hidden="true" />
          <Link to={b.url || "/"} className="inapp__text" onClick={() => done(b)}>
            <strong>{b.title}</strong>{b.body ? <span>{b.body}</span> : null}
          </Link>
          <button type="button" className="icon-link" aria-label={`Dismiss ${b.title}`} onClick={() => done(b)}><X size={15} aria-hidden="true" /></button>
        </div>
      ))}
    </div>
  );
}

/** Tests: forget what this page has already reported. */
export function resetSeen() { queue = new Set(); sent.clear(); if (timer) clearTimeout(timer); timer = null; }
