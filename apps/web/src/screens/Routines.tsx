import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Clapperboard, Droplets, Fuel as FuelIcon, Gauge, Mountain, PackageCheck, Plus, Thermometer, Trash2, Users } from "lucide-react";
import { Glass } from "../components/Glass";
import { SeenMark, today as seenToday } from "../components/Smart";
import { PageHead } from "../components/PageHead";
import { useResource } from "../api/resource";
import { assistant } from "../api/hub";
import {
  routines, type Bin, type BinKind, type Bins, type Bedroom, type Catchups, type Containers, type Fuel, type Garden, type Internet,
  type RouteKind, type Tonight, type Weekend, type WeekendRoute, type WeekendWindow, type ContainerEvent, type ContainerHistory } from "../api/routines";

/** 10.4: cards for the week's routines on Home, two for Home Lab, and the "Around the week" screen that sets them up. */

const DAY = (iso: string, style: "short" | "long" = "short") => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: style });
const ampm = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}${m ? `:${String(m).padStart(2, "0")}` : ""}${h < 12 ? "am" : "pm"}`;
};
const BIN_LABEL: Record<BinKind, string> = { rubbish: "Rubbish", recycling: "Recycling", green: "Green waste", glass: "Glass" };
const KIND_LABEL: Record<RouteKind, string> = { run: "Run", hike: "Hike", ride: "Ride", walk: "Walk", other: "Other" };
const SETUP = <Link to="/week" className="widget__source">Set up</Link>;

// -- Home ---------------------------------------------------------------------------------------------------------

/** Thursday to Sunday: the weekend's best dry, free hours and a route that fits each. */
export function WeekendCard() {
  const day = new Date().getDay();
  const on = day === 0 || day >= 4;
  const res = useResource<Weekend>("routines:weekend", () => routines.weekend(), { staleMs: 30 * 60_000, persist: true, enabled: on });
  const w = res.data;
  if (!on || !w || !Array.isArray(w.windows)) return null;
  const best = w.windows.slice(0, 3);
  return (
    <Glass as="section" className="widget" aria-label="This weekend">
      <header className="widget__head"><Mountain aria-hidden="true" /><span>This weekend</span><SeenMark k={`weekend:${w.days[0]}`} />{SETUP}</header>
      {best.length === 0 ? <p className="muted" style={{ margin: 0 }}>{w.note ?? "No dry, free daylight this weekend."}</p> : (
        <ul className="items">
          {best.map((x) => <WindowRow key={`${x.date}${x.start}`} w={x} />)}
        </ul>
      )}
      {w.recover && <p className="muted" style={{ margin: 0, fontSize: 12 }}>Readiness says recover, so these are the easy ones.</p>}
      {w.routes.length === 0 && best.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 12 }}>Add your usual routes and each window gets one that fits.</p>}
    </Glass>
  );
}

function WindowRow({ w }: { w: WeekendWindow }) {
  const r = w.route;
  return (
    <li className="item">
      <span className="item__text">
        <span className="item__title">{DAY(w.date)} {ampm(w.start)}–{ampm(w.end)}</span>
        <span className="item__subtitle">{w.conditions}, {Math.round(w.low_c)}–{Math.round(w.high_c)}°{r ? ` · ${r.name} (${r.hours} h)` : ""}</span>
      </span>
      {r?.link && <a className="button button--small" href={r.link} target="_blank" rel="noreferrer">Route</a>}
    </li>
  );
}

/** From 6pm: what to watch before bed, and what's new this week. */
export function WatchTonightCard() {
  const evening = new Date().getHours() >= 18;
  const res = useResource<Tonight>("routines:tonight", () => routines.tonight(), { staleMs: 15 * 60_000, enabled: evening });
  const t = res.data;
  if (!evening || !t || !t.available || !Array.isArray(t.picks)) return null;
  const eps = Array.isArray(t.episodes) ? t.episodes : [];
  const films = Array.isArray(t.movies) ? t.movies : [];
  if (t.picks.length === 0 && eps.length === 0 && films.length === 0) return null;
  return (
    <Glass as="section" className="widget" aria-label="Watch tonight">
      <header className="widget__head"><Clapperboard aria-hidden="true" /><span>Watch tonight</span>
        {t.minutes_to_bed != null && <span className="widget__source">{hm(t.minutes_to_bed)} till bed</span>}</header>
      {t.picks.length > 0 && (
        <ul className="items">
          {t.picks.map((p) => (
            <li key={p.title} className="item"><span className="item__text"><span className="item__title">{p.title}</span>
              {p.why && <span className="item__subtitle">{p.why}</span>}</span></li>
          ))}
        </ul>
      )}
      {(eps.length > 0 || films.length > 0) && (
        <div style={{ fontSize: 13 }}>
          <strong style={{ fontSize: 12 }} className="muted">New this week</strong>
          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
            {eps.slice(0, 5).map((e, i) => <li key={`e${i}`}>{e.series}{e.season != null && e.number != null ? ` S${String(e.season).padStart(2, "0")}E${String(e.number).padStart(2, "0")}` : ""}{e.air_date ? ` · ${DAY(e.air_date.slice(0, 10))}` : ""}</li>)}
            {films.slice(0, 3).map((m, i) => <li key={`m${i}`}>{m.title}{m.kind ? ` (${m.kind})` : ""}</li>)}
          </ul>
        </div>
      )}
    </Glass>
  );
}

const short = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
const hm = (mins: number) => (mins >= 60 ? `${Math.floor(mins / 60)} h${mins % 60 ? ` ${mins % 60} min` : ""}` : `${mins} min`);

/** The evening before collection and that morning. */
export function BinsCard() {
  const res = useResource<Bins>("routines:bins", () => routines.bins(), { staleMs: 30 * 60_000, persist: true });
  const b = res.data;
  if (!b || !b.show || !b.next) return null;
  return (
    <Glass as="section" className="widget" aria-label="Bins">
      <header className="widget__head"><Trash2 aria-hidden="true" /><span>Bins out {b.when ?? ""}</span><SeenMark k={`bins:${b.next.date}`} />{SETUP}</header>
      <p style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>{b.next.text}</p>
    </Glass>
  );
}

/** Around bedtime: is the bedroom ready, and the temperature you sleep best at. */
export function BedroomCard() {
  const res = useResource<Bedroom>("routines:bedroom", () => routines.bedroom(), { staleMs: 10 * 60_000 });
  const b = res.data;
  if (!b || !b.show) return null;
  return (
    <Glass as="section" className="widget" aria-label="Bedroom">
      <header className="widget__head"><Thermometer aria-hidden="true" /><span>Bedroom</span><SeenMark k={`bedroom:${seenToday()}`} />{SETUP}</header>
      <p style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>{b.temp != null ? `${b.temp}°` : "No reading"}{b.humidity != null ? <span className="muted" style={{ fontSize: 14 }}> · {Math.round(b.humidity)}% humidity</span> : null}</p>
      {b.advice && <p style={{ margin: 0 }}>{b.advice}</p>}
      {b.best && <p className="muted" style={{ margin: 0, fontSize: 12 }}>You sleep best at {b.best.low}–{b.best.high}°: {b.best.sleep} h against {b.best.other} h ({b.best.nights} nights).</p>}
    </Glass>
  );
}

/** Mornings: water or not, from the rain that's fallen and is coming. */
export function GardenCard() {
  const res = useResource<Garden>("routines:garden", () => routines.garden(), { staleMs: 60 * 60_000, persist: true });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const g = res.data;
  const today = new Date().toLocaleDateString("en-CA");
  if (!g || !g.on || !g.water || g.last_watered === today) return null;
  return (
    <Glass as="section" className="widget" aria-label="Garden">
      <header className="widget__head"><Droplets aria-hidden="true" /><span>Water the garden</span><SeenMark k={`garden:${seenToday()}`} />{SETUP}</header>
      <p style={{ margin: 0 }}>{g.why}</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {g.protocol && (
          <button type="button" className="button button--small button--primary" disabled={busy} onClick={async () => {
            setBusy(true);
            try { await assistant.runProtocol(g.protocol!); res.mutate(await routines.watered()); } catch { setMsg("Couldn't start it."); } finally { setBusy(false); }
          }}>Water now</button>
        )}
        <button type="button" className="button button--small" disabled={busy} onClick={async () => res.mutate(await routines.watered())}>Done</button>
      </div>
      {msg && <p className="tone-critical" style={{ margin: 0, fontSize: 12 }}>{msg}</p>}
    </Glass>
  );
}

/** The evening before the Shepparton drive and that morning: the cheapest fuel in the drive's first stretch. */
export function FuelCard() {
  const res = useResource<Fuel>("routines:fuel", () => routines.fuel(), { staleMs: 60 * 60_000, persist: true });
  const f = res.data;
  // 11.8.0: on the day it's for, it shows even when it can't find a price (no key, Fair Fuel down), saying why, instead
  // of quietly not being there.
  if (!f || !f.for) return null;
  return (
    <Glass as="section" className="widget" aria-label="Fuel on the way">
      <header className="widget__head"><FuelIcon aria-hidden="true" /><span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={`To ${f.settings.destination.name}`}>Fuel on the way</span><SeenMark k={`fuel:${f.for}`} />{SETUP}</header>
      <FuelBody f={f} />
    </Glass>
  );
}

function FuelBody({ f }: { f: Fuel }) {
  const options = Array.isArray(f.options) ? f.options : [];
  if (f.error) return <p className="tone-critical" style={{ margin: 0 }}>{f.error}</p>;
  if (!f.best) return <p className="muted" style={{ margin: 0 }}>{f.why || `No ${f.settings.fuel_type} prices in the first ${f.settings.first_km} km.`}</p>;
  return (
    <>
      <p style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>{f.best.name} · {f.best.price.toFixed(1)}¢</p>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>{f.best.km_in} km in{f.best.off_km >= 0.3 ? `, ${f.best.off_km} km off the road` : ""}{f.saving_cents ? ` · ${f.saving_cents}¢ under the average on the way` : ""}</p>
      {options.length > 1 && (
        <ul className="items">
          {options.slice(0, 4).map((o) => (
            <li key={o.id} className="item"><span className="item__text"><span className="item__title">{o.name}</span>
              <span className="item__subtitle">{o.price.toFixed(1)}¢ · {o.km_in} km in</span></span>
              <a className="button button--small" href={o.maps} target="_blank" rel="noreferrer">Map</a></li>
          ))}
        </ul>
      )}
      <p className="muted" style={{ margin: 0, fontSize: 11 }}>{f.note} {f.attribution}</p>
    </>
  );
}

/** Friday to Sunday: who's overdue a catch-up and the free parts of the weekend. */
export function CatchupsCard() {
  const day = new Date().getDay();
  const on = day === 0 || day >= 5;
  const res = useResource<Catchups>("routines:catchups", () => routines.catchups(), { staleMs: 60 * 60_000, enabled: on });
  const c = res.data;
  if (!on || !c || !Array.isArray(c.overdue) || c.overdue.length === 0) return null;
  const free = Array.isArray(c.free) ? c.free.slice(0, 3).map((x) => `${DAY(x.date, "long")} ${x.part}`) : [];
  return (
    <Glass as="section" className="widget" aria-label="Catch-ups">
      <header className="widget__head"><Users aria-hidden="true" /><span>Catch up</span><SeenMark k={`catchup:${seenToday()}`} /></header>
      <ul className="items">
        {c.overdue.slice(0, 3).map((p) => (
          <li key={p.id} className="item"><span className="item__text"><span className="item__title">{p.name}</span>
            <span className="item__subtitle">{p.days_since != null ? `${p.days_since} days since` : "Not yet"} · every {p.gap} days</span></span>
            <button type="button" className="button button--small" onClick={async () => res.mutate(await routines.caughtUp(p.id))}>Caught up</button></li>
        ))}
      </ul>
      {free.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 12 }}>Free: {free.join(", ")}</p>}
    </Glass>
  );
}

// -- Home Lab -----------------------------------------------------------------------------------------------------

/** Containers with a newer image, updated one at a time by SirisAI. */
export function ContainerUpdatesCard() {
  const res = useResource<Containers>("routines:containers", () => routines.containers(), { staleMs: 10 * 60_000 });
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const d = res.data;
  if (!d) return null;
  const updates = Array.isArray(d.updates) ? d.updates : [];
  const run = async (names: string[], label: string) => {
    setBusy(label); setMsg(null);
    try { setMsg((await routines.updateContainers(names)).message); res.mutate({ ...d, running: true }); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't start the update."); } finally { setBusy(null); }
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Container updates">
      <header className="widget__head"><PackageCheck aria-hidden="true" /><span>Container updates</span>
        <button type="button" className="widget__source icon-link" disabled={busy !== null} onClick={async () => {
          setBusy("check");
          try { res.mutate(await routines.checkContainers()); } catch { setMsg("Couldn't check."); } finally { setBusy(null); }
        }}>{busy === "check" ? "Checking…" : "Check now"}</button></header>
      {!d.available ? <p className="muted" style={{ margin: 0 }}>SirisAI can't see Docker.</p> : updates.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>Everything's up to date{d.checked_at ? ` (checked ${new Date(d.checked_at).toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" })})` : ""}.</p>
      ) : (
        <>
          <ul className="items">
            {updates.map((u) => (
              <li key={u.container} className="item"><span className="item__text"><span className="item__title">{u.container}</span>
                <span className="item__subtitle">{[u.image, u.current && u.available ? `${u.current} → ${u.available}` : null].filter(Boolean).join(" · ")}</span></span>
                <button type="button" className="button button--small" disabled={busy !== null || d.running} onClick={() => run([u.container], u.container)}>Update</button></li>
            ))}
          </ul>
          {updates.length > 1 && <button type="button" className="button button--small button--primary" style={{ alignSelf: "flex-start" }} disabled={busy !== null || d.running} onClick={() => run([], "all")}>Update all</button>}
        </>
      )}
      {d.running && <p className="muted" style={{ margin: 0, fontSize: 12 }}>Updating now: SirisAI tells you when it's done.</p>}
      {msg && <p style={{ margin: 0, fontSize: 12 }}>{msg}</p>}
      <ContainerHistoryList busy={busy !== null || d.running} />
    </Glass>
  );
}

const WHAT: Record<string, string> = { updated: "Updated", "put back": "Put back", "rolled back": "Rolled back", failed: "Failed", "up to date": "Already current" };

/** 11.19: what's happened lately, with a roll-back for each container's last update, and the ones held back. */
function ContainerHistoryList({ busy }: { busy: boolean }) {
  const res = useResource<ContainerHistory>("routines:containers:history", () => routines.containerHistory(), { staleMs: 60_000 });
  const [msg, setMsg] = useState<string | null>(null);
  const d = res.data;
  if (!d) return null;
  const history = Array.isArray(d.history) ? d.history : [];
  const latest = new Map<string, ContainerEvent>();
  for (const e of history) if (!latest.has(e.container)) latest.set(e.container, e);
  const act = async (name: string, action: "roll-back" | "update") => {
    setMsg(null);
    try {
      const r = await routines.containerAction(name, action);
      setMsg(r.started ? (action === "roll-back" ? `Putting ${name} back: SirisAI tells you when it's done.` : `Updating ${name}: SirisAI tells you when it's done.`) : r.why ?? "It didn't start.");
    } catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't start it."); }
  };
  return (
    <>
      {Array.isArray(d.held) && d.held.length > 0 && (
        <>
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }}>Held on an earlier version (left out of updates until you update it):</p>
          <ul className="items">
            {d.held.map((n) => (
              <li key={n} className="item"><span className="item__text"><span className="item__title">{n}</span></span>
                <button type="button" className="button button--small" disabled={busy} onClick={() => void act(n, "update")}>Update now</button></li>
            ))}
          </ul>
        </>
      )}
      {history.length > 0 && (
        <details>
          <summary className="muted" style={{ fontSize: 13, cursor: "pointer" }}>Recent changes ({history.length})</summary>
          <ul className="items" aria-label="Recent container changes">
            {history.slice(0, 15).map((e, i) => (
              <li key={`${e.at}-${e.container}-${i}`} className="item">
                <span className="item__text">
                  <span className="item__title">{e.container} · {WHAT[e.status] ?? e.status}</span>
                  <span className="item__subtitle">{new Date(e.at).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}
                    {e.trigger !== "update" ? ` · ${e.trigger}` : ""}{e.also.length ? ` · with ${e.also.join(", ")}` : ""}{e.why ? ` · ${e.why}` : ""}</span>
                </span>
                {e.status === "updated" && e.before && latest.get(e.container) === e && (
                  <button type="button" className="button button--small" disabled={busy} aria-label={`Roll back ${e.container}`}
                    onClick={() => { if (window.confirm(`Put ${e.container} back on the version it had before this update? It stays there until you update it.`)) void act(e.container, "roll-back"); }}>Roll back</button>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
      {msg && <p style={{ margin: 0, fontSize: 12 }} role="status">{msg}</p>}
    </>
  );
}

/** The speed tests' daily median against the plan, and dropouts. */
export function InternetCard() {
  const res = useResource<Internet>("routines:internet", () => routines.internet(), { staleMs: 10 * 60_000 });
  const [down, setDown] = useState("");
  const d = res.data;
  useEffect(() => { if (d?.plan?.down != null) setDown(String(d.plan.down)); }, [d?.plan?.down]);
  if (!d || !d.available) return null;
  const days = Array.isArray(d.daily) ? d.daily : [];
  const outages = Array.isArray(d.outages) ? d.outages : [];
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Internet speed">
      <header className="widget__head"><Gauge aria-hidden="true" /><span>Internet speed</span><SeenMark k={(d.slow ?? []).length ? `internet-slow:${seenToday()}` : null} />
        {d.share_of_plan != null && <span className="widget__source">{d.share_of_plan}% of plan lately</span>}</header>
      {days.length === 0 ? <p className="muted" style={{ margin: 0 }}>No speed tests yet.</p> : <SpeedChart days={days} plan={d.plan?.down ?? null} slow={d.slow ?? []} />}
      {(d.slow ?? []).length > 0 && <p className="muted" style={{ margin: 0, fontSize: 12 }}>Orange days were under half the plan.</p>}
      {outages.length > 0 && (
        <p style={{ margin: 0, fontSize: 13 }}>{outages.length} dropout{outages.length === 1 ? "" : "s"}, the last {new Date(outages[outages.length - 1].start).toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" })} for {hm(Math.max(1, Math.round(outages[outages.length - 1].seconds / 60)))}.</p>
      )}
      <form style={{ display: "flex", gap: 8, alignItems: "center" }} onSubmit={async (e) => {
        e.preventDefault();
        const n = Number(down);
        res.mutate(await routines.setPlan(down.trim() && n > 0 ? n : null, d.plan?.up ?? null));
      }}>
        <label className="muted" style={{ fontSize: 13 }} htmlFor="plan-down">Plan (Mbps down)</label>
        <input id="plan-down" className="field" inputMode="numeric" style={{ width: 90 }} value={down} onChange={(e) => setDown(e.target.value)} />
        <button type="submit" className="button button--small">Save</button>
      </form>
    </Glass>
  );
}

function SpeedChart({ days, plan, slow }: { days: Internet["daily"]; plan: number | null; slow: string[] }) {
  const W = 320, H = 120, pad = 18;
  const top = Math.max(plan ?? 0, ...days.map((x) => x.down)) * 1.1 || 1;
  const bw = Math.max(4, Math.min(28, (W - pad) / days.length - 2));
  const y = (v: number) => H - pad - (v / top) * (H - pad - 6);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Daily download speed for ${days.length} days${plan ? ` against a ${plan} Mbps plan` : ""}`}>
      <line x1={pad} x2={W} y1={H - pad} y2={H - pad} stroke="currentColor" strokeOpacity={0.15} />
      {days.map((x, i) => {
        const cx = pad + i * ((W - pad) / days.length) + 1;
        const h = Math.max(2, H - pad - y(x.down));
        return (
          <g key={x.date}>
            <rect x={cx} y={H - pad - h} width={bw} height={h} rx={Math.min(4, bw / 2)} fill={slow.includes(x.date) ? "var(--warning)" : "var(--accent)"}>
              <title>{`${DAY(x.date)} ${x.date.slice(5)}: ${x.down} down, ${x.up} up (${x.tests} test${x.tests === 1 ? "" : "s"})`}</title>
            </rect>
          </g>
        );
      })}
      {plan != null && (
        <>
          <line x1={pad} x2={W} y1={y(plan)} y2={y(plan)} stroke="currentColor" strokeOpacity={0.5} strokeDasharray="4 3" />
          <text x={W} y={y(plan) - 4} textAnchor="end" fontSize={10} fill="currentColor" opacity={0.7}>Plan {plan}</text>
        </>
      )}
      <text x={pad} y={H - 4} fontSize={10} fill="currentColor" opacity={0.6}>{short(days[0].date)}</text>
      <text x={W} y={H - 4} fontSize={10} textAnchor="end" fill="currentColor" opacity={0.6}>{short(days[days.length - 1].date)}</text>
    </svg>
  );
}

// -- Around the week (set-up) -------------------------------------------------------------------------------------

export function WeekScreen() {
  useEffect(() => { document.title = "Around the week · SirisOS"; }, []);
  return (
    <>
      <PageHead eyebrow="Set up the week's routines" title="Around the week" />
      <div className="stack" style={{ marginTop: 16 }}>
        <RoutesSetup />
        <FuelSetup />
        <BinsSetup />
        <BedroomSetup />
        <GardenSetup />
      </div>
    </>
  );
}

function RoutesSetup() {
  const res = useResource<Weekend>("routines:weekend", () => routines.weekend(), { staleMs: 30 * 60_000, persist: true });
  const [name, setName] = useState(""); const [kind, setKind] = useState<RouteKind>("walk"); const [hours, setHours] = useState("1"); const [link, setLink] = useState("");
  const routes: WeekendRoute[] = Array.isArray(res.data?.routes) ? res.data!.routes : [];
  const save = async (next: Partial<WeekendRoute>[]) => res.mutate(await routines.setRoutes(next));
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Weekend routes">
      <header className="widget__head"><Mountain aria-hidden="true" /><span>Weekend routes</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Thursday evening, SirisOS picks the weekend's dry, free hours and the route that fits each. A walk when readiness says recover.</p>
      <ul className="items">
        {routes.map((r) => (
          <li key={r.id} className="item"><span className="item__text"><span className="item__title">{r.name}</span>
            <span className="item__subtitle">{KIND_LABEL[r.kind]} · {r.hours} h{r.km ? ` · ${r.km} km` : ""}</span></span>
            <button type="button" className="button button--small" aria-label={`Remove ${r.name}`} onClick={() => save(routes.filter((x) => x.id !== r.id))}>Remove</button></li>
        ))}
      </ul>
      <form style={{ display: "flex", gap: 8, flexWrap: "wrap" }} onSubmit={async (e) => {
        e.preventDefault();
        if (!name.trim()) return;
        await save([...routes, { name: name.trim(), kind, hours: Number(hours) || 1, link: link.trim() || null }]);
        setName(""); setLink("");
      }}>
        <input className="field" aria-label="Route name" placeholder="Route name" value={name} onChange={(e) => setName(e.target.value)} style={{ flex: "1 1 160px" }} maxLength={80} />
        <select className="field" aria-label="Kind" value={kind} onChange={(e) => setKind(e.target.value as RouteKind)} style={{ width: "auto" }}>
          {(Object.keys(KIND_LABEL) as RouteKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
        </select>
        <input className="field" aria-label="Hours" inputMode="decimal" value={hours} onChange={(e) => setHours(e.target.value)} style={{ width: 64 }} />
        <input className="field" aria-label="Link (optional)" placeholder="Link (optional)" value={link} onChange={(e) => setLink(e.target.value)} style={{ flex: "1 1 160px" }} />
        <button type="submit" className="button button--small"><Plus size={13} aria-hidden="true" /> Add</button>
      </form>
    </Glass>
  );
}

function FuelSetup() {
  const res = useResource<Fuel>("routines:fuel", () => routines.fuel(), { staleMs: 60 * 60_000, persist: true });
  const f = res.data;
  if (!f) return null;
  const s = f.settings;
  const set = async (body: Parameters<typeof routines.setFuel>[0]) => res.mutate(await routines.setFuel(body));
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Fuel on the way">
      <header className="widget__head"><FuelIcon aria-hidden="true" /><span>Fuel on the way to {s.destination.name}</span></header>
      {!f.configured ? <p className="muted" style={{ margin: 0 }}>{f.why}</p> : <FuelBody f={f} />}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", fontSize: 13 }}>
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}><input type="checkbox" checked={s.on} onChange={(e) => set({ on: e.target.checked })} /> On</label>
        <select className="field" aria-label="Day" value={s.weekday} onChange={(e) => set({ weekday: Number(e.target.value) })} style={{ width: "auto" }}>
          {["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((d, i) => <option key={d} value={i}>{d}</option>)}
        </select>
        <input className="field" type="time" aria-label="Leave at" value={s.leave} onChange={(e) => e.target.value && set({ leave: e.target.value })} style={{ width: "auto" }} />
        <select className="field" aria-label="Fuel" value={s.fuel_type} onChange={(e) => set({ fuel_type: e.target.value })} style={{ width: "auto" }}>
          {[["U91", "Unleaded 91"], ["P95", "Premium 95"], ["P98", "Premium 98"], ["E10", "E10"], ["DSL", "Diesel"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>First
          <input className="field" inputMode="numeric" aria-label="First kilometres" defaultValue={s.first_km} style={{ width: 60 }} onBlur={(e) => Number(e.target.value) > 0 && set({ first_km: Number(e.target.value) })} /> km</label>
      </div>
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>Shown the evening before and that morning, with a notification 30 minutes before you leave. The route starts from {s.home ? "your home" : "where SirisAI's weather is for"}.</p>
    </Glass>
  );
}

function BinsSetup() {
  const res = useResource<Bins>("routines:bins", () => routines.bins(), { staleMs: 30 * 60_000, persist: true });
  const [kind, setKind] = useState<BinKind>("rubbish"); const [every, setEvery] = useState("1"); const [first, setFirst] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const bins: Bin[] = Array.isArray(res.data?.bins) ? res.data!.bins : [];
  const save = async (next: Bin[]) => {
    setErr(null);
    try { res.mutate(await routines.setBins(next)); } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't save."); }
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Bins">
      <header className="widget__head"><Trash2 aria-hidden="true" /><span>Bin night</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        {res.data?.next ? `Next: ${res.data.next.text}, ${DAY(res.data.next.date, "long")}.` : "Add each bin and a day it was collected."} A notification at 7pm the night before.
      </p>
      <ul className="items">
        {bins.map((b, i) => (
          <li key={`${b.kind}${i}`} className="item"><span className="item__text"><span className="item__title">{BIN_LABEL[b.kind]}</span>
            <span className="item__subtitle">{b.every_weeks === 1 ? "Every week" : `Every ${b.every_weeks} weeks`} · {DAY(b.first, "long")}s</span></span>
            <button type="button" className="button button--small" aria-label={`Remove ${BIN_LABEL[b.kind]}`} onClick={() => save(bins.filter((_, j) => j !== i))}>Remove</button></li>
        ))}
      </ul>
      <form style={{ display: "flex", gap: 8, flexWrap: "wrap" }} onSubmit={async (e) => { e.preventDefault(); if (first) await save([...bins, { kind, every_weeks: Number(every), first }]); }}>
        <select className="field" aria-label="Bin" value={kind} onChange={(e) => setKind(e.target.value as BinKind)} style={{ width: "auto" }}>
          {(Object.keys(BIN_LABEL) as BinKind[]).map((k) => <option key={k} value={k}>{BIN_LABEL[k]}</option>)}
        </select>
        <select className="field" aria-label="How often" value={every} onChange={(e) => setEvery(e.target.value)} style={{ width: "auto" }}>
          <option value="1">Every week</option><option value="2">Fortnightly</option><option value="4">Every 4 weeks</option>
        </select>
        <input className="field" type="date" aria-label="A collection day" value={first} onChange={(e) => setFirst(e.target.value)} style={{ width: "auto" }} />
        <button type="submit" className="button button--small" disabled={!first}><Plus size={13} aria-hidden="true" /> Add</button>
      </form>
      {err && <p className="tone-critical" style={{ margin: 0, fontSize: 12 }}>{err}</p>}
    </Glass>
  );
}

function BedroomSetup() {
  const res = useResource<Bedroom>("routines:bedroom", () => routines.bedroom(), { staleMs: 10 * 60_000 });
  const b = res.data;
  const [temp, setTemp] = useState(""); const [hum, setHum] = useState(""); const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (b) { setTemp(b.temp_entity ?? ""); setHum(b.humidity_entity ?? ""); } }, [b?.temp_entity, b?.humidity_entity]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!b) return null;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Bedroom">
      <header className="widget__head"><Thermometer aria-hidden="true" /><span>Bedroom before bed</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>From an hour before bed, the bedroom's temperature and whether to cool or warm it. After two weeks, the temperature you sleep best at.</p>
      <form className="stack" style={{ gap: 8 }} onSubmit={async (e) => {
        e.preventDefault(); setErr(null);
        try { res.mutate(await routines.setBedroom({ temp_entity: temp.trim() || null, humidity_entity: hum.trim() || null })); }
        catch (x) { setErr(x instanceof Error ? x.message : "Couldn't save."); }
      }}>
        <input className="field" aria-label="Temperature sensor" placeholder="Temperature sensor (e.g. sensor.bedroom_temperature)" value={temp} onChange={(e) => setTemp(e.target.value)} />
        <input className="field" aria-label="Humidity sensor" placeholder="Humidity sensor (optional)" value={hum} onChange={(e) => setHum(e.target.value)} />
        <button type="submit" className="button button--small" style={{ alignSelf: "flex-start" }}>Save</button>
      </form>
      {b.temp != null && <p style={{ margin: 0, fontSize: 13 }}>Now {b.temp}°{b.humidity != null ? `, ${Math.round(b.humidity)}%` : ""}.</p>}
      {b.best ? <p style={{ margin: 0, fontSize: 13 }}>You sleep best at {b.best.low}–{b.best.high}°.</p>
        : b.temp_entity && <p className="muted" style={{ margin: 0, fontSize: 12 }}>{b.nights ?? 0} of 14 nights recorded for your best temperature.</p>}
      {err && <p className="tone-critical" style={{ margin: 0, fontSize: 12 }}>{err}</p>}
    </Glass>
  );
}

function GardenSetup() {
  const res = useResource<Garden>("routines:garden", () => routines.garden(), { staleMs: 60 * 60_000, persist: true });
  const [protocol, setProtocol] = useState("");
  const g = res.data;
  useEffect(() => { setProtocol(g?.protocol ?? ""); }, [g?.protocol]);
  if (!g) return null;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Garden">
      <header className="widget__head"><Droplets aria-hidden="true" /><span>Garden and rain</span></header>
      <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 14 }}>
        <input type="checkbox" checked={g.on} onChange={async (e) => res.mutate(await routines.setGarden({ on: e.target.checked }))} /> Tell me in the morning when to water
      </label>
      {g.on && g.why && <p style={{ margin: 0, fontSize: 13 }}>Today: {g.why}</p>}
      <form style={{ display: "flex", gap: 8 }} onSubmit={async (e) => { e.preventDefault(); res.mutate(await routines.setGarden({ protocol: protocol.trim() || null })); }}>
        <input className="field" aria-label="Watering protocol" placeholder="SirisAI protocol that waters (optional)" value={protocol} onChange={(e) => setProtocol(e.target.value)} style={{ flex: 1, minWidth: 0 }} />
        <button type="submit" className="button button--small">Save</button>
      </form>
    </Glass>
  );
}

