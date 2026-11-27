import { useEffect, useState } from "react";
import { CalendarDays, CloudSun, Package, Trash2, UtensilsCrossed } from "lucide-react";
import { api } from "../api/client";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

/** The wall display's feed (11.15): read with the wall's own key, never your sign-in. */
export interface WallFeed {
  now: string; phase: string; dim: boolean;
  weather: { summary?: string; condition?: string; high?: number; low?: number; max_c?: number; min_c?: number; rain_chance?: number } | null;
  today: { title: string; start: string; end?: string | null; all_day: boolean }[];
  tomorrow: { title: string; start: string; all_day: boolean }[];
  bins: { next: { date: string; text: string } | null; when?: string | null } | null;
  dinner: { title: string } | null;
  parcels: { name: string; status: string; eta?: string | null }[];
}

const KEY = "sirisos.wall.key";
const time = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

function readKey(): string {
  const fromUrl = new URLSearchParams(window.location.search).get("key");
  try {
    if (fromUrl) { localStorage.setItem(KEY, fromUrl); return fromUrl; }
    return localStorage.getItem(KEY) ?? "";
  } catch { return fromUrl ?? ""; }
}

/** A spare tablet in the kitchen (11.15): the time, today's weather, today's and tomorrow's events, bin night, dinner and
 * parcels, in big type. It never signs in: it opens with the wall's key, which reads nothing else. It keeps the
 * screen on, checks again every minute, and dims from wind-down to the morning (a tap brightens it for a minute). */
export function WallScreen() {
  const [key] = useState(readKey);
  const [now, setNow] = useState(() => new Date());
  const [woken, setWoken] = useState(0);
  const [feed, setFeed] = useState<WallFeed | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { document.title = "Wall · SirisOS"; }, []);
  useEffect(() => { const t = window.setInterval(() => setNow(new Date()), 15_000); return () => window.clearInterval(t); }, []);
  useEffect(() => {
    if (!key) return undefined;
    const load = async () => {
      try {
        const r = await fetch(`/api/v1/wall?key=${encodeURIComponent(key)}`);
        if (r.status === 401) { setError("This wall's key isn't right any more: make a new one on SirisOS's Security page."); return; }
        if (!r.ok) throw new Error(String(r.status));
        setFeed(await r.json() as WallFeed);
        setError(null);
      } catch { /* the server's away: keep showing the last */ }
    };
    void load();
    const t = window.setInterval(load, 60_000);
    return () => window.clearInterval(t);
  }, [key]);
  // Keep the screen on (and ask again when the page comes back).
  useEffect(() => {
    let lock: { release: () => Promise<void> } | null = null;
    const ask = async () => {
      try { lock = await (navigator as Navigator & { wakeLock?: { request: (t: "screen") => Promise<{ release: () => Promise<void> }> } }).wakeLock?.request("screen") ?? null; } catch { /* not allowed */ }
    };
    void ask();
    const back = () => { if (document.visibilityState === "visible") void ask(); };
    document.addEventListener("visibilitychange", back);
    return () => { document.removeEventListener("visibilitychange", back); void lock?.release().catch(() => {}); };
  }, []);

  if (!key) return <div className="wall wall--empty"><p>Open this page with the wall's address from SirisOS's Security page (Wall display).</p></div>;
  const dim = !!feed?.dim && Date.now() - woken > 60_000;
  const w = feed?.weather;
  const high = w?.high ?? w?.max_c;
  const low = w?.low ?? w?.min_c;
  return (
    <div className={`wall${dim ? " wall--dim" : ""}`} onClick={() => setWoken(Date.now())} role="main" aria-label="Wall display">
      <header className="wall__clock">
        <div className="wall__time">{now.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}</div>
        <div className="wall__date">{now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</div>
      </header>
      {error && <p className="wall__error" role="alert">{error}</p>}
      {feed && (
        <div className="wall__grid">
          <Glass as="section" className="widget wall__card" aria-label="Weather">
            <header className="widget__head"><CloudSun aria-hidden="true" /><span>Weather</span></header>
            {w ? <p className="wall__big">{high != null ? `${Math.round(high)}°` : ""}{low != null ? <span className="muted"> / {Math.round(low)}°</span> : null}
              <span className="wall__sub">{w.summary ?? w.condition ?? ""}{w.rain_chance != null ? ` · ${Math.round(w.rain_chance)}% rain` : ""}</span></p>
              : <p className="muted">No forecast.</p>}
          </Glass>
          <Glass as="section" className="widget wall__card wall__card--wide" aria-label="Today">
            <header className="widget__head"><CalendarDays aria-hidden="true" /><span>Today</span></header>
            {feed.today.length ? (
              <ul className="wall__events">{feed.today.map((e) => <li key={`${e.start}${e.title}`}><span>{e.all_day ? "All day" : time(e.start)}</span>{e.title}</li>)}</ul>
            ) : <p className="muted">Nothing on today.</p>}
            {feed.tomorrow.length > 0 && <p className="wall__sub">Tomorrow: {feed.tomorrow.map((e) => `${e.all_day ? "" : `${time(e.start)} `}${e.title}`).join(" · ")}</p>}
          </Glass>
          <Glass as="section" className="widget wall__card" aria-label="Dinner">
            <header className="widget__head"><UtensilsCrossed aria-hidden="true" /><span>Dinner</span></header>
            <p className="wall__mid">{feed.dinner?.title ?? <span className="muted">Not planned</span>}</p>
          </Glass>
          <Glass as="section" className="widget wall__card" aria-label="Bins">
            <header className="widget__head"><Trash2 aria-hidden="true" /><span>Bins</span></header>
            {feed.bins?.next ? <p className="wall__mid">{feed.bins.next.text}<span className="wall__sub">{feed.bins.when ?? new Date(`${feed.bins.next.date}T12:00:00`).toLocaleDateString(undefined, { weekday: "long" })}</span></p>
              : <p className="muted">No bins set up.</p>}
          </Glass>
          {feed.parcels.length > 0 && (
            <Glass as="section" className="widget wall__card" aria-label="Parcels">
              <header className="widget__head"><Package aria-hidden="true" /><span>Parcels</span></header>
              <ul className="wall__events">{feed.parcels.map((p) => <li key={p.name}><span>{p.status}</span>{p.name}</li>)}</ul>
            </Glass>
          )}
        </div>
      )}
    </div>
  );
}

/** Security → Wall display (11.15): make the wall's key and its address, shown once. */
export function WallKeyCard() {
  const res = useResource<{ on: boolean; made: string | null }>("wall:key", () => api("/api/v1/wall/key"), {});
  const [made, setMade] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const on = !!res.data?.on;
  const make = async () => {
    if (on && !window.confirm("Make a new wall address? The tablet using the old one stops until you open the new one on it.")) return;
    setBusy(true);
    try { const got = await api<{ key: string; path: string }>("/api/v1/wall/key", { method: "POST" }); setMade(`${window.location.origin}${got.path}`); await res.reload(true); }
    finally { setBusy(false); }
  };
  const off = async () => { if (!window.confirm("Turn the wall display off?")) return; setBusy(true); try { await api("/api/v1/wall/key", { method: "DELETE" }); setMade(null); await res.reload(true); } finally { setBusy(false); } };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Wall display">
      <header className="widget__head"><CalendarDays aria-hidden="true" /><span>Wall display</span>{on && <span className="widget__source tone-good">On</span>}</header>
      <p style={{ margin: 0, fontSize: 14 }}>For a spare tablet in the kitchen: the time, weather, today's events, bin night, dinner and parcels, always on, dimmed at night. The tablet doesn't sign in: its address carries a key that reads only that.</p>
      {made && (
        <>
          <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>Open this on the tablet now (and add it to its Home Screen): it won't be shown again.</p>
          <code className="gym-key" aria-label="Wall address">{made}</code>
          <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => void navigator.clipboard?.writeText(made)}>Copy the address</button>
        </>
      )}
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" className={`button ${on ? "" : "button--primary"}`} disabled={busy} onClick={make}>{on ? "Make a new address" : "Set up a wall display"}</button>
        {on && <button type="button" className="chip chip--button" disabled={busy} onClick={off}>Turn off</button>}
      </div>
    </Glass>
  );
}
