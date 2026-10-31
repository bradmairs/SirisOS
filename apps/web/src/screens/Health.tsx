import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Activity, BatteryMedium, BedDouble, Database, Dumbbell, Gauge, HeartPulse, Lightbulb, Moon, NotebookPen, Scale, Target, ThermometerSun, TrendingUp } from "lucide-react";
import { BAND_TONE, health, type Energy, type Goal, type Health, type LogKind, type Point, type Readiness, type Trend, type Vital } from "../api/health";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";

const VIEWS = [{ id: "today", label: "Today" }, { id: "sleep", label: "Sleep" }, { id: "fitness", label: "Fitness" }, { id: "vitals", label: "Vitals" },
  { id: "log", label: "Log" }, { id: "data", label: "Data" }] as const;
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
    <div className="rring" style={{ width: size, height: size }} role="img" aria-label={`Readiness ${r.score} out of 100, ${r.band}`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={radius} className="rring__track" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={radius} className={`rring__arc ${BAND_TONE[r.band]}`} strokeWidth={stroke}
          strokeDasharray={`${(r.score / 100) * length} ${length}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <div className="rring__label"><span className="rring__score">{r.score}</span><span className={`rring__band ${BAND_TONE[r.band]}`}>{r.band}</span></div>
    </div>
  );
}

const energyTone = (v: number) => (v >= 60 ? "tone-good" : v >= 30 ? "tone-warning" : "tone-critical");
const lockedNote = (r: Readiness) => (r.locked ? "Kept from this morning" : "Settles once last night's data is in");

/** The day's energy (5.9): where it is now, and the line since waking. */
export function EnergyMeter({ e, compact = false }: { e: Energy; compact?: boolean }) {
  const W = 240, H = 44;
  const pts = e.timeline;
  const x = (i: number) => (pts.length > 1 ? (i / (pts.length - 1)) * W : W);
  const y = (v: number) => H - (v / 100) * H;
  return (
    <div className="energy">
      <div className="energy__head">
        <span className={`hud-big ${energyTone(e.now)}`}>{e.now}</span>
        <span className="muted energy__of">/ 100 · started at {e.start} ({e.wake})</span>
      </div>
      <div className="energy__bar" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={e.now} aria-label={`Energy ${e.now} out of 100`}>
        <span className={`energy__fill ${energyTone(e.now)}`} style={{ width: `${e.now}%` }} />
      </div>
      {!compact && pts.length > 1 && (
        <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="Energy since waking">
          <polyline points={pts.map((p, i) => `${x(i)},${y(p.value)}`).join(" ")} className="spark__line" />
          <circle cx={x(pts.length - 1)} cy={y(pts[pts.length - 1].value)} r={3} className="spark__dot" />
        </svg>
      )}
      <p style={{ margin: 0, fontSize: 14 }}>{e.summary}</p>
      {!compact && (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          Spent {e.spent.activity} on activity, {e.spent.stress} on stress and {e.spent.awake} just being awake; got {e.regained} back resting.
          {e.estimated ? " Estimated from the day's totals: set Health Auto Export to aggregate by hour for a live line." : ""}
        </p>
      )}
    </div>
  );
}

/** Home and the brief (5.7): today's readiness. Hidden until there's a score. */
export function ReadinessWidget() {
  const res = useResource("health:today", () => health.today(), { staleMs: 15 * 60_000, persist: true });
  const r = res.data?.readiness;
  const e = res.data?.energy;
  if (!r) return null;
  return (
    <Glass as="section" className="widget" aria-label="Readiness">
      <header className="widget__head"><Gauge aria-hidden="true" /><span>Readiness</span><Link to="/health" className="widget__source">Health</Link></header>
      <div className="row readiness-row"><ReadinessRing r={r} size={96} /><p style={{ margin: 0, fontSize: 14 }}>{r.advice}</p></div>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>{r.summary}{r.early ? " · Early days: it sharpens after a week of data." : ""}</p>
      {e && <><div className="widget__head energy__label"><BatteryMedium aria-hidden="true" /><span>Energy now</span></div><EnergyMeter e={e} compact /></>}
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
      {h && !h.available && view !== "data" && (
        <Glass className="widget" style={{ marginTop: 16, minHeight: 0 }}>
          <p style={{ margin: 0 }}>{h.guest_mode ? "Health is hidden in guest mode." : !h.sources.sirisai ? "SirisAI isn't answering, so there's no health data to show."
            : <>No health data yet. Set up Apple Health on the <Link to="/training#health" className="brief-link">Training page</Link>, or bring in your history from the Data tab.</>}</p>
        </Glass>
      )}
      {h?.migrating && <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>Moving your earlier health history into SirisAI…</p>}
      {h && view === "data" && <div className="stack" style={{ marginTop: 16 }}><DataView onChange={() => res.reload?.()} /></div>}
      {h?.available && view !== "data" && (
        <div className="stack" style={{ marginTop: 16 }}>
          {view === "today" && <TodayView h={h} />}
          {view === "sleep" && <SleepView h={h} />}
          {view === "fitness" && <FitnessView h={h} />}
          {view === "vitals" && <VitalsView h={h} />}
          {view === "log" && <LogView h={h} onChange={() => res.reload?.()} />}
        </div>
      )}
    </>
  );
}

function TodayView({ h }: { h: Health }) {
  const r = h.readiness;
  return (
    <>
      {h.getting_sick && (
        <div className="error-banner" role="alert" style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <ThermometerSun aria-hidden="true" />
          <span>{h.getting_sick.level === "early"
            ? <>Early signs you may be getting run down: {h.getting_sick.today.join(", ")}. An easy day and an early night help; training eases off today.</>
            : <>Your body may be fighting something off: {h.getting_sick.today.join(", ")}. Go easy today; the training plan rests.</>}</span>
        </div>
      )}
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Readiness today">
        <header className="widget__head"><Gauge aria-hidden="true" /><span>Readiness</span></header>
        {r ? (
          <>
            <div className="row readiness-row">
              <ReadinessRing r={r} />
              <div style={{ display: "grid", gap: 6 }}>
                <p style={{ margin: 0, fontSize: 16 }}>{r.advice}</p>
                {r.early && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Early days: SirisOS needs a week of your data to know your usual, so this sharpens soon.</p>}
                <p className="muted" style={{ margin: 0, fontSize: 13 }}>From last night's sleep, overnight HRV and vitals. {lockedNote(r)}.</p>
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
      {h.energy && (
        <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Energy">
          <header className="widget__head"><BatteryMedium aria-hidden="true" /><span>Energy</span></header>
          <EnergyMeter e={h.energy} />
        </Glass>
      )}
      {h.trends && h.trends.length > 0 && <TrendsCard trends={h.trends} />}
      <div className="widget-grid">
        <Tile title="Sleep" Icon={BedDouble} to="/health?view=sleep" big={hm(h.sleep.last_night?.hours)} sub={h.sleep.score != null ? `Sleep score ${h.sleep.score} · need ${hm(h.sleep.need)}` : `You need about ${hm(h.sleep.need)}`} />
        <Tile title="Training load" Icon={Dumbbell} to="/health?view=fitness" big={h.activity.load.ratio != null ? h.activity.load.ratio.toFixed(2) : "–"} sub={h.activity.load.zone ? `This week against the last four: ${h.activity.load.zone}` : "Needs a few weeks of exercise data"} />
        <Tile title="Today" Icon={Activity} to="/health?view=fitness" big={h.activity.steps != null ? Math.round(h.activity.steps).toLocaleString() : "–"} sub={`steps · ${Math.round(h.activity.exercise_minutes ?? 0)} min exercise · ${Math.round(h.activity.active_energy_kcal ?? 0)} kcal`} />
        {h.bedtime && <Tile title="Tonight" Icon={Moon} to="/health?view=sleep" big={h.bedtime.bedtime} sub={h.bedtime.text} />}
        {h.weight && <Tile title="Weight" Icon={Scale} to="/health?view=vitals" big={`${h.weight.trend.toFixed(1)} kg`}
          sub={`Trend, ${h.weight.per_week >= 0 ? "+" : ""}${h.weight.per_week.toFixed(2)} kg a week${h.weight.to_go_kg != null ? ` · ${h.weight.to_go_kg} kg to go${h.weight.weeks_to_goal ? `, about ${h.weight.weeks_to_goal} weeks` : ""}` : ""}`} />}
      </div>
      {!!h.insights?.length && (
        <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="What your sleep goes with">
          <header className="widget__head"><Lightbulb aria-hidden="true" /><span>What your sleep goes with</span></header>
          <ul className="items">{h.insights.map((i) => <li key={i.factor} className="item"><span className={`item__dot ${i.minutes < 0 ? "dot-warning" : "dot-good"}`} aria-hidden="true" /><span className="item__text"><span className="item__title career-wrap">{i.text}</span></span></li>)}</ul>
        </Glass>
      )}
    </>
  );
}

/** This week against your last 30 days (6.1): what's moving, and whether that's good. */
function TrendsCard({ trends }: { trends: Trend[] }) {
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="This week">
      <header className="widget__head"><TrendingUp aria-hidden="true" /><span>This week against your month</span></header>
      <ul className="items">
        {trends.map((t) => (
          <li key={t.key} className="item">
            <span className="item__text">
              <span className="item__title">{t.label}</span>
              <span className="item__subtitle">{t.week}{t.unit ? ` ${t.unit}` : ""} a day, usually {t.baseline}{t.unit ? ` ${t.unit}` : ""}</span>
            </span>
            <span className={`trend ${t.good === true ? "tone-good" : t.good === false ? "tone-warning" : "muted"}`}>
              {t.direction === "steady" ? "steady" : `${t.direction === "up" ? "▲" : "▼"} ${Math.abs(t.change_pct)}%`}
            </span>
          </li>
        ))}
      </ul>
    </Glass>
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
      <GoalsCard />
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


const GOAL_METRICS: [string, string][] = [["running_km", "km run"], ["walk_run_km", "km walked or run"], ["exercise_minutes", "minutes of exercise"], ["steps", "steps"]];

/** Goals tied to a health number (5.8): progress and pace, worked out by SirisAI from the data. */
function GoalsCard() {
  const res = useResource("health:goals", () => health.goals(), { staleMs: 10 * 60_000 });
  const year = new Date().getFullYear();
  const [metric, setMetric] = useState("running_km");
  const [target, setTarget] = useState("");
  const [end, setEnd] = useState(`${year}-12-31`);
  const [error, setError] = useState<string | null>(null);
  const goals: Goal[] = Array.isArray(res.data?.goals) ? res.data!.goals : [];
  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await health.addGoal({ metric, target: Number(target), end });
      setTarget("");
      res.reload?.();
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
  }
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Goals">
      <header className="widget__head"><Target aria-hidden="true" /><span>Goals</span></header>
      {goals.length ? (
        <ul className="items">
          {goals.map((g) => (
            <li key={g.goal_id} className="item contributor">
              <span className="item__text">
                <span className="item__title career-wrap">{g.title}</span>
                <span className="career-bar" role="presentation"><span className={`career-bar__fill ${g.on_pace ? "career-bar__fill--good" : ""}`} style={{ width: `${Math.min(100, g.percent ?? 0)}%` }} /></span>
                <span className="item__subtitle">{Math.round(g.done).toLocaleString()} so far · {g.on_pace ? "on pace" : g.needed_per_week ? `behind: ${Math.round(g.needed_per_week).toLocaleString()} a week to make it` : "behind"}</span>
              </span>
            </li>
          ))}
        </ul>
      ) : <p className="muted" style={{ margin: 0, fontSize: 14 }}>No goals yet. "Run 1,000 km this year" works.</p>}
      <form className="row" style={{ gap: 8, flexWrap: "wrap" }} onSubmit={add}>
        <input className="input" type="number" min={1} required placeholder="Target" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Target" style={{ width: 110 }} />
        <select className="input" value={metric} onChange={(e) => setMetric(e.target.value)} aria-label="What">{GOAL_METRICS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <label className="muted" style={{ fontSize: 13 }}>by <input className="input" type="date" required value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        <button className="btn" type="submit">Add goal</button>
      </form>
      {error && <div className="error-banner" role="alert">{error}</div>}
    </Glass>
  );
}

const QUICK: { label: string; kind: LogKind; amount: number }[] = [
  { label: "+250 ml water", kind: "water", amount: 250 }, { label: "+500 ml water", kind: "water", amount: 500 },
  { label: "Coffee", kind: "caffeine", amount: 80 }, { label: "A drink", kind: "alcohol", amount: 1 },
];

/** Quick logs (5.8): water, coffee, drinks, mood, symptoms and supplements, kept by SirisAI. Voice works too. */
function LogView({ h, onChange }: { h: Health; onChange: () => void }) {
  const [text, setText] = useState("");
  const [kind, setKind] = useState<LogKind>("symptom");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  async function run(fn: () => Promise<unknown>, done: string) {
    setBusy(true); setNote(null);
    try { await fn(); setNote(done); onChange(); } catch (e) { setNote(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  const l = h.logged;
  return (
    <>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Today's log">
        <header className="widget__head"><NotebookPen aria-hidden="true" /><span>Today</span></header>
        <div className="metrics metrics--compact">
          <div><div className="metric__value">{l?.water_ml ? `${(l.water_ml / 1000).toFixed(2)} L` : "–"}</div><div className="metric__label">Water</div></div>
          <div><div className="metric__value">{l?.caffeine_mg ? `${Math.round(l.caffeine_mg)} mg` : "–"}</div><div className="metric__label">Caffeine</div></div>
          <div><div className="metric__value">{l?.alcohol_drinks ?? "–"}</div><div className="metric__label">Drinks</div></div>
          <div><div className="metric__value">{l?.mood ?? "–"}</div><div className="metric__label">Mood (1-5)</div></div>
        </div>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          {QUICK.map((q) => <button key={q.label} type="button" className="chip chip--button" disabled={busy} onClick={() => run(() => health.log(q.kind, q.amount), `Logged ${q.label.toLowerCase()}`)}>{q.label}</button>)}
          {[1, 2, 3, 4, 5].map((m) => <button key={m} type="button" className="chip chip--button" disabled={busy} aria-label={`Mood ${m} of 5`} onClick={() => run(() => health.log("mood", m), `Mood ${m}`)}>Mood {m}</button>)}
        </div>
        <form className="row" style={{ gap: 8, flexWrap: "wrap" }} onSubmit={(e) => { e.preventDefault(); if (text.trim()) run(() => health.log(kind, undefined, text.trim()), "Noted").then(() => setText("")); }}>
          <select className="input" value={kind} onChange={(e) => setKind(e.target.value as LogKind)} aria-label="Kind">
            {["symptom", "supplement", "medication", "feeling", "note"].map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
          <input className="input" placeholder="Headache since lunch, took vitamin D…" value={text} onChange={(e) => setText(e.target.value)} maxLength={500} style={{ flex: 1, minWidth: 180 }} aria-label="Note" />
          <button className="btn" type="submit" disabled={busy}>Log</button>
        </form>
        <label className="muted" style={{ fontSize: 13 }}>A meal photo, for a rough estimate:{" "}
          <input type="file" accept="image/*" capture="environment" disabled={busy} onChange={(e) => { const f = e.target.files?.[0]; if (f) run(() => health.meal(f), "Meal logged (a rough estimate)"); }} /></label>
        {note && <p className="muted" role="status" style={{ margin: 0 }}>{note}</p>}
      </Glass>
      {!!l?.notes?.length && (
        <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="This week's notes">
          <header className="widget__head"><NotebookPen aria-hidden="true" /><span>This week</span></header>
          <ul className="items">{l.notes.map((n) => <li key={n.id} className="item"><span className="item__text"><span className="item__title career-wrap">{n.text}</span><span className="item__subtitle">{day(n.day)} · {n.kind}</span></span></li>)}</ul>
        </Glass>
      )}
    </>
  );
}

/** Your data (5.8): years of history from the Health app, export, a summary for a doctor, and deleting a range. */
function DataView({ onChange }: { onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  async function run(fn: () => Promise<string>) {
    setBusy(true); setNote(null);
    try { setNote(await fn()); onChange(); } catch (e) { setNote(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Your health data">
      <header className="widget__head"><Database aria-hidden="true" /><span>Your health data</span></header>
      <p style={{ margin: 0, fontSize: 14 }}>Bring in years of history: in the Health app, tap your picture, then <strong>Export All Health Data</strong>, and choose the <code>export.zip</code> here. Days Health Auto Export already sent keep its values.</p>
      <input type="file" accept=".zip,.xml" disabled={busy} aria-label="Apple Health export"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) run(async () => { const r = await health.backfill(f); return `Brought in ${r.days} days${r.from ? ` from ${day(r.from)}` : ""} and ${r.workouts} workouts.`; }); }} />
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn" disabled={busy} onClick={() => run(async () => { await health.download("/api/v1/health/export.csv", "health.csv"); return "Exported."; })}>Export CSV</button>
        <button type="button" className="btn" disabled={busy} onClick={() => run(async () => { await health.report(); return "The summary opened in a new tab; print it to save a PDF."; })}>Summary for a doctor</button>
      </div>
      <form className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}
        onSubmit={(e) => { e.preventDefault(); if (window.confirm(`Delete all health data from ${start} to ${end}? This can't be undone.`)) run(async () => { const r = await health.remove(start, end); return `Deleted ${r.readings} readings and ${r.workouts} workouts.`; }); }}>
        <span className="muted" style={{ fontSize: 13 }}>Delete from</span>
        <input className="input" type="date" required value={start} onChange={(e) => setStart(e.target.value)} aria-label="From" />
        <span className="muted" style={{ fontSize: 13 }}>to</span>
        <input className="input" type="date" required value={end} onChange={(e) => setEnd(e.target.value)} aria-label="To" />
        <button className="btn btn--danger" type="submit" disabled={busy}>Delete</button>
      </form>
      {note && <p className="muted" role="status" style={{ margin: 0 }}>{note}</p>}
    </Glass>
  );
}
