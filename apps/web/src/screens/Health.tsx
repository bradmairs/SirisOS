import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Activity, BedDouble, Dumbbell, Gauge, HeartPulse } from "lucide-react";
import { BAND_TONE, health, type Health, type Point, type Readiness, type Vital } from "../api/health";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";

const VIEWS = [{ id: "today", label: "Today" }, { id: "sleep", label: "Sleep" }, { id: "fitness", label: "Fitness" }, { id: "vitals", label: "Vitals" }] as const;
type View = (typeof VIEWS)[number]["id"];
const day = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
const hm = (h: number | null | undefined) => (h == null ? "–" : `${Math.floor(h)}h ${String(Math.round((h % 1) * 60)).padStart(2, "0")}m`);
const clock = (stamp: string | null) => {
  const m = stamp?.match(/(\d{2}):(\d{2})/);
  if (!m) return null;
  const h = Number(m[1]);
  return `${((h + 11) % 12) + 1}:${m[2]} ${h < 12 ? "am" : "pm"}`;
};

/** The readiness score as a ring: the arc is the score out of 100. */
export function ReadinessRing({ r, size = 132 }: { r: Readiness; size?: number }) {
  const stroke = size / 11, radius = (size - stroke) / 2, length = 2 * Math.PI * radius;
  return (
    <div className="ring" style={{ width: size, height: size }} role="img" aria-label={`Readiness ${r.score} out of 100, ${r.band}`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} className="ring__track" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={radius} className={`ring__arc ${BAND_TONE[r.band]}`} strokeWidth={stroke}
          strokeDasharray={`${(r.score / 100) * length} ${length}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <div className="ring__label"><span className="ring__score">{r.score}</span><span className={`ring__band ${BAND_TONE[r.band]}`}>{r.band}</span></div>
    </div>
  );
}

/** Home and the brief (5.7): today's readiness. Hidden until there's a score. */
export function ReadinessWidget() {
  const res = useResource("health:today", () => health.today(), { staleMs: 15 * 60_000, persist: true });
  const r = res.data?.readiness;
  if (!r) return null;
  return (
    <Glass as="section" className="widget" aria-label="Readiness">
      <header className="widget__head"><Gauge aria-hidden="true" /><span>Readiness</span><Link to="/health" className="widget__source">Health</Link></header>
      <div className="row readiness-row"><ReadinessRing r={r} size={96} /><p style={{ margin: 0, fontSize: 14 }}>{r.advice}</p></div>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>{r.summary}{r.early ? " · Early days: it sharpens after a week of data." : ""}</p>
    </Glass>
  );
}

export function HealthScreen() {
  const res = useResource<Health>("health", () => health.get(), { refreshMs: 10 * 60_000, staleMs: 60_000, persist: true });
  const [params, setParams] = useSearchParams();
  const view = (VIEWS.find((v) => v.id === params.get("view"))?.id ?? "today") as View;
  useEffect(() => { document.title = "Health · SirisOS"; }, []);
  const h = res.data;
  return (
    <>
      <PageHead eyebrow={h ? `${h.sources.days} days of data${h.sources.health_auto_export ? " · Apple Health" : ""}` : "Health"} title="Health" />
      <div className="row career-views" role="tablist" aria-label="Health views">
        {VIEWS.map((v) => (
          <button key={v.id} type="button" role="tab" aria-selected={view === v.id} className={`chip chip--button ${view === v.id ? "chip--active" : ""}`}
            onClick={() => setParams(v.id === "today" ? {} : { view: v.id }, { replace: true })}>{v.label}</button>
        ))}
      </div>
      {!h && res.error && <div className="error-banner" role="alert">{res.error}</div>}
      {!h && !res.error && <div className="skeleton" style={{ height: 220, marginTop: 16 }} aria-busy="true" />}
      {h && !h.available && (
        <Glass className="widget" style={{ marginTop: 16, minHeight: 0 }}>
          <p style={{ margin: 0 }}>No health data yet. Set up Apple Health on the <Link to="/training#health" className="brief-link">Training page</Link> and it fills in from the next sync.</p>
        </Glass>
      )}
      {h?.available && (
        <div className="stack" style={{ marginTop: 16 }}>
          {view === "today" && <TodayView h={h} />}
          {view === "sleep" && <SleepView h={h} />}
          {view === "fitness" && <FitnessView h={h} />}
          {view === "vitals" && <VitalsView h={h} />}
        </div>
      )}
    </>
  );
}

function TodayView({ h }: { h: Health }) {
  const r = h.readiness;
  return (
    <>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Readiness today">
        <header className="widget__head"><Gauge aria-hidden="true" /><span>Readiness</span></header>
        {r ? (
          <>
            <div className="row readiness-row">
              <ReadinessRing r={r} />
              <div style={{ display: "grid", gap: 6 }}>
                <p style={{ margin: 0, fontSize: 16 }}>{r.advice}</p>
                {r.early && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Early days: SirisOS needs a week of your data to know your usual, so this sharpens soon.</p>}
              </div>
            </div>
            <ul className="items">
              {r.contributors.map((c) => (
                <li key={c.key} className="item contributor">
                  <span className="item__text">
                    <span className="item__title career-wrap">{c.text}</span>
                    <span className="career-bar" role="presentation"><span className={`career-bar__fill ${c.score >= 60 ? "career-bar__fill--good" : ""}`} style={{ width: `${c.score}%` }} /></span>
                  </span>
                  <span className="muted contributor__score">{c.score}</span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted" style={{ margin: 0 }}>No score yet: it needs last night's sleep or HRV, and a few days of history.</p>
        )}
      </Glass>
      <div className="widget-grid">
        <Tile title="Sleep" Icon={BedDouble} to="/health?view=sleep" big={hm(h.sleep.last_night?.hours)} sub={h.sleep.score != null ? `Sleep score ${h.sleep.score} · need ${hm(h.sleep.need)}` : `You need about ${hm(h.sleep.need)}`} />
        <Tile title="Training load" Icon={Dumbbell} to="/health?view=fitness" big={h.activity.load.ratio != null ? h.activity.load.ratio.toFixed(2) : "–"} sub={h.activity.load.zone ? `This week against the last four: ${h.activity.load.zone}` : "Needs a few weeks of exercise data"} />
        <Tile title="Today" Icon={Activity} to="/health?view=fitness" big={h.activity.steps != null ? Math.round(h.activity.steps).toLocaleString() : "–"} sub={`steps · ${Math.round(h.activity.exercise_minutes ?? 0)} min exercise · ${Math.round(h.activity.active_energy_kcal ?? 0)} kcal`} />
      </div>
    </>
  );
}

function Tile({ title, Icon, to, big, sub }: { title: string; Icon: typeof Gauge; to: string; big: string; sub: string }) {
  return (
    <Glass as="section" className="widget" aria-label={title}>
      <header className="widget__head"><Icon aria-hidden="true" /><span>{title}</span><Link to={to} className="widget__source">More</Link></header>
      <span className="hud-big">{big}</span>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>{sub}</p>
    </Glass>
  );
}

/** One series as bars, with a reference line; hover or focus a bar for its value. */
function Bars({ points, label, unit, line, lineLabel, format = (v) => `${Math.round(v)}${unit}` }: {
  points: Point[]; label: string; unit: string; line?: number | null; lineLabel?: string; format?: (v: number) => string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(line ?? 0, ...points.map((p) => p.value ?? 0), 1) * 1.1;
  const shown = hover ?? points.length - 1;
  const p = points[shown];
  return (
    <div className="hbars">
      <p className="muted hbars__readout" aria-live="polite">{day(p.date)}: <strong>{p.value != null ? format(p.value) : "no data"}</strong>{line != null && lineLabel ? ` · ${lineLabel} ${format(line)}` : ""}</p>
      <div className="hbars__plot" role="list" aria-label={label} onMouseLeave={() => setHover(null)}>
        {line != null && <span className="hbars__line" style={{ bottom: `${(line / max) * 100}%` }} aria-hidden="true" />}
        {points.map((pt, i) => (
          <span key={pt.date} role="listitem" tabIndex={0} aria-label={`${day(pt.date)}: ${pt.value != null ? format(pt.value) : "no data"}`}
            className={`hbars__bar ${i === shown ? "hbars__bar--on" : ""}`} onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)}>
            <span style={{ height: `${pt.value ? Math.max(2, (pt.value / max) * 100) : 0}%` }} />
          </span>
        ))}
      </div>
    </div>
  );
}

function SleepView({ h }: { h: Health }) {
  const s = h.sleep, n = s.last_night;
  const stages = n && [["Deep", n.deep], ["REM", n.rem], ["Core", n.core], ["Awake", n.awake]].filter(([, v]) => v != null) as [string, number][];
  return (
    <>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Last night">
        <header className="widget__head"><BedDouble aria-hidden="true" /><span>Last night</span></header>
        {n ? (
          <>
            <div className="metrics">
              <div><div className="metric__value">{hm(n.hours)}</div><div className="metric__label">Asleep</div></div>
              <div><div className="metric__value">{s.score ?? "–"}</div><div className="metric__label">Sleep score</div></div>
              <div><div className="metric__value">{hm(s.need)}</div><div className="metric__label">You need</div></div>
            </div>
            {stages && stages.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 14 }}>{stages.map(([k, v]) => `${k} ${hm(v)}`).join(" · ")}</p>}
            {(n.start || n.end) && <p className="muted" style={{ margin: 0, fontSize: 14 }}>Asleep {clock(n.start) ?? "?"} to {clock(n.end) ?? "?"}{n.in_bed ? ` · ${hm(n.in_bed)} in bed` : ""}</p>}
          </>
        ) : <p className="muted" style={{ margin: 0 }}>No sleep recorded last night yet.</p>}
      </Glass>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Two weeks of sleep">
        <header className="widget__head"><BedDouble aria-hidden="true" /><span>Two weeks</span></header>
        <Bars points={s.nights.map((x) => ({ date: x.date, value: x.hours }))} label="Hours asleep each night" unit=" h" format={hm} line={s.need} lineLabel="need" />
        <div className="metrics metrics--compact">
          <div><div className="metric__value">{hm(s.average_7d)}</div><div className="metric__label">7-night average</div></div>
          <div><div className="metric__value">{hm(s.debt_7d)}</div><div className="metric__label">Sleep debt this week</div></div>
          <div><div className="metric__value">{s.bedtime_spread_min != null ? `±${s.bedtime_spread_min} min` : "–"}</div><div className="metric__label">Bedtime regularity</div></div>
        </div>
      </Glass>
    </>
  );
}

function FitnessView({ h }: { h: Health }) {
  const a = h.activity;
  return (
    <>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Training load">
        <header className="widget__head"><Dumbbell aria-hidden="true" /><span>Training load</span></header>
        <div className="metrics">
          <div><div className="metric__value">{a.load.ratio != null ? a.load.ratio.toFixed(2) : "–"}</div><div className="metric__label">{a.load.zone ?? "Not enough data"}</div></div>
          <div><div className="metric__value">{Math.round(a.load.acute_min_per_day)} min</div><div className="metric__label">A day this week</div></div>
          <div><div className="metric__value">{Math.round(a.load.chronic_min_per_day)} min</div><div className="metric__label">A day, last 4 weeks</div></div>
        </div>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>0.8 to 1.3 is the sweet spot: enough to improve without a jump that invites injury.</p>
        <Bars points={a.exercise_series} label="Exercise minutes each day" unit=" min" line={a.load.chronic_min_per_day || null} lineLabel="4-week average" />
      </Glass>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Steps">
        <header className="widget__head"><Activity aria-hidden="true" /><span>Steps</span></header>
        <Bars points={a.steps_series} label="Steps each day" unit="" format={(v) => Math.round(v).toLocaleString()} />
      </Glass>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Workouts">
        <header className="widget__head"><Dumbbell aria-hidden="true" /><span>Workouts</span><Link to="/training" className="widget__source">Training</Link></header>
        {a.workouts.length ? (
          <ul className="items">
            {a.workouts.map((w) => (
              <li key={w.date + w.start + w.name} className="item">
                <span className="item__dot dot-good" aria-hidden="true" />
                <span className="item__text"><span className="item__title">{w.name}</span>
                  <span className="item__subtitle">{[day(w.date), w.minutes && `${w.minutes} min`, w.km && `${w.km} km`, w.kcal && `${w.kcal} kcal`, w.avg_hr && `${Math.round(w.avg_hr)} bpm avg`].filter(Boolean).join(" · ")}</span></span>
              </li>
            ))}
          </ul>
        ) : <p className="muted" style={{ margin: 0, fontSize: 14 }}>No workouts yet: include Workouts in Health Auto Export.</p>}
      </Glass>
    </>
  );
}

/** A 30-day line with the usual range (baseline ± spread) shaded behind it. */
function Spark({ v }: { v: Vital }) {
  const pts = v.series.map((p, i) => ({ i, y: p.value })).filter((p): p is { i: number; y: number } => p.y != null);
  if (pts.length < 2) return null;
  const lo = Math.min(...pts.map((p) => p.y), v.baseline != null && v.spread != null ? v.baseline - v.spread : Infinity);
  const hi = Math.max(...pts.map((p) => p.y), v.baseline != null && v.spread != null ? v.baseline + v.spread : -Infinity);
  const W = 240, H = 48, pad = (hi - lo) * 0.15 || 1;
  const x = (i: number) => (i / (v.series.length - 1)) * W;
  const y = (val: number) => H - ((val - lo + pad) / (hi - lo + 2 * pad)) * H;
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={`${v.label} over 30 days`}>
      {v.baseline != null && v.spread != null && <rect x={0} width={W} y={y(v.baseline + v.spread)} height={Math.max(1, y(v.baseline - v.spread) - y(v.baseline + v.spread))} className="spark__band" />}
      <polyline points={pts.map((p) => `${x(p.i)},${y(p.y)}`).join(" ")} className="spark__line" />
      <circle cx={x(pts[pts.length - 1].i)} cy={y(pts[pts.length - 1].y)} r={3} className="spark__dot" />
    </svg>
  );
}

function VitalsView({ h }: { h: Health }) {
  if (!h.vitals.length) return <p className="muted">No vitals yet.</p>;
  return (
    <div className="widget-grid">
      {h.vitals.map((v) => (
        <Glass as="section" key={v.key} className="widget" style={{ minHeight: 0 }} aria-label={v.label}>
          <header className="widget__head"><HeartPulse aria-hidden="true" /><span>{v.label}</span>
            {v.state !== "normal" && <span className="widget__source tone-warning">{v.state === "high" ? "Above your usual" : "Below your usual"}</span>}</header>
          <div className="row" style={{ alignItems: "baseline", gap: 6 }}><span className="hud-big">{v.value}</span><span className="muted">{v.unit}</span></div>
          <Spark v={v} />
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>{v.baseline != null ? `Your usual ${v.baseline}${v.spread ? ` ± ${v.spread}` : ""} ${v.unit}` : "Building your usual"}{v.date !== h.today ? ` · from ${day(v.date)}` : ""}</p>
        </Glass>
      ))}
    </div>
  );
}
