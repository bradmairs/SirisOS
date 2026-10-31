import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { CalendarPlus, CircleAlert, CircleCheck, Copy, Footprints, HeartPulse, KeyRound, Trophy } from "lucide-react";
import { DISTANCES, training, type HealthImportStatus, type Race, type Training } from "../api/training";
import { useResource } from "../api/resource";
import { health, type Health } from "../api/health";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";

const day = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
const LEVEL: Record<Training["recovery"]["level"], string> = { good: "Recovered: train as planned", easy: "Recovery's down: take it easier", rest: "Rest today" };

function copy(text: string) {
  navigator.clipboard?.writeText(text).catch(() => undefined);
}

/** On Home (5.5): today's run from the plan, or rest, adjusted for recovery. Hidden without a race. */
export function TodaysRunWidget() {
  const res = useResource<Training>("training", () => training.get(), { staleMs: 30 * 60_000, persist: true });
  const t = res.data;
  if (!t?.plan) return null;
  return (
    <Glass as="section" className="widget" aria-label="Today's run">
      <header className="widget__head"><Footprints aria-hidden="true" /><span>Today's run</span>
        <Link to="/training" className="widget__source">{t.plan.days_to_go} days to {t.plan.race.name}</Link></header>
      <div className="item__title career-wrap">{t.session ? t.session.title : t.recovery.level === "rest" ? "Rest today" : "No run planned today"}</div>
      {t.recovery.notes.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{t.recovery.notes.join(" · ")}</p>}
      {t.this_week && <p className="muted" style={{ margin: 0, fontSize: 13 }}>This week: {t.this_week.done_km ?? 0} of {t.this_week.km} km</p>}
    </Glass>
  );
}

export function TrainingScreen() {
  const res = useResource<Training>("training", () => training.get(), { staleMs: 60_000, persist: true });
  const t = res.data;
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { document.title = "Training · SirisOS"; }, []);

  async function save(r: Race | null) {
    try {
      res.mutate(r ? await training.setRace(r) : await training.clearRace());
      setEditing(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save.");
    }
  }

  return (
    <>
      <PageHead eyebrow="Running" title="Training" />
      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="stack" style={{ marginTop: 16 }}>
        {t && !t.plan && !editing && (
          <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Your next race">
            <header className="widget__head"><Trophy aria-hidden="true" /><span>Your next race</span></header>
            <p className="muted" style={{ margin: 0 }}>Add a race and SirisOS builds a plan from what you've been running ({t.recent_weekly_km} km a week lately), then adjusts each day for how you've slept and recovered.</p>
            <button type="button" className="button button--primary" style={{ alignSelf: "flex-start", justifySelf: "start" }} onClick={() => setEditing(true)}>Add a race</button>
          </Glass>
        )}
        {editing && <RaceForm race={t?.plan?.race ?? null} onSave={save} onCancel={() => setEditing(false)} onDelete={t?.plan ? () => save(null) : undefined} />}
        {t?.plan && !editing && <PlanCard t={t} onEdit={() => setEditing(true)} />}
        {t?.plan && <FeedCard />}
        <HealthImportCard health={t?.health ?? false} />
      </div>
    </>
  );
}

function RaceForm({ race, onSave, onCancel, onDelete }: { race: Race | null; onSave: (r: Race) => void; onCancel: () => void; onDelete?: () => void }) {
  const [f, setF] = useState<Race>(race ?? { name: "", date: "", distance_km: 10, goal_time: "" });
  const [ownStart, setOwnStart] = useState(race?.start_km != null ? String(race.start_km) : "");
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!f.name.trim() || !f.date) return;
    onSave({ ...f, name: f.name.trim(), start_km: ownStart ? Number(ownStart) : null });
  }
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Race">
      <form className="stack maint__form" onSubmit={submit}>
        <header className="widget__head"><Trophy aria-hidden="true" /><span>{race ? "Change the race" : "Add a race"}</span></header>
        <input className="field" value={f.name} placeholder="e.g. Run Melbourne" aria-label="Race" onChange={(e) => setF({ ...f, name: e.target.value })} />
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
          <input className="field" type="date" value={f.date} aria-label="Race day" onChange={(e) => setF({ ...f, date: e.target.value })} style={{ flex: "1 1 150px" }} />
          <select className="field" aria-label="Distance" value={f.distance_km} onChange={(e) => setF({ ...f, distance_km: Number(e.target.value) })} style={{ flex: "1 1 150px" }}>
            {DISTANCES.map(([km, label]) => <option key={km} value={km}>{label}</option>)}
          </select>
          <input className="field" value={f.goal_time ?? ""} placeholder="Goal time (optional)" aria-label="Goal time" onChange={(e) => setF({ ...f, goal_time: e.target.value })} style={{ flex: "1 1 150px" }} />
        </div>
        <input className="field" inputMode="decimal" value={ownStart} placeholder="Start from (km a week; blank: your recent running)" aria-label="Start from, km a week" onChange={(e) => setOwnStart(e.target.value)} />
        <div className="row" style={{ gap: 8 }}>
          <button type="submit" className="button button--primary" disabled={!f.name.trim() || !f.date}>Save</button>
          <button type="button" className="button" onClick={onCancel}>Cancel</button>
          {onDelete && <button type="button" className="button" style={{ marginLeft: "auto" }} onClick={onDelete}>Remove the race</button>}
        </div>
      </form>
    </Glass>
  );
}

function PlanCard({ t, onEdit }: { t: Training; onEdit: () => void }) {
  const p = t.plan!;
  const peak = Math.max(...p.weeks.map((w) => w.km), 1);
  return (
    <>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Today">
        <header className="widget__head"><HeartPulse aria-hidden="true" /><span>Today</span>
          <button type="button" className="widget__source icon-link" onClick={onEdit}>Change</button></header>
        <div className="item__title career-wrap" style={{ fontSize: 18 }}>{t.session ? t.session.title : t.recovery.level === "rest" ? "Rest today" : "No run planned today"}</div>
        <p className={t.recovery.level === "good" ? "muted" : "tone-warning"} style={{ margin: 0, fontSize: 14 }}>
          {t.recovery.known ? LEVEL[t.recovery.level] : "No sleep or heart data from last night yet"}{t.recovery.notes.length ? `: ${t.recovery.notes.join("; ")}.` : ""}
        </p>
        <div className="metrics">
          <div><div className="metric__value">{p.days_to_go}</div><div className="metric__label">Days to {p.race.name}</div></div>
          <div><div className="metric__value">{t.this_week ? `${t.this_week.done_km ?? 0}/${t.this_week.km}` : "–"}</div><div className="metric__label">km this week</div></div>
          <div><div className="metric__value">{p.start_km}</div><div className="metric__label">km/week at the start</div></div>
          {t.prediction && <div><div className="metric__value">{t.prediction.time}</div><div className="metric__label">Predicted, from {t.prediction.from}</div></div>}
        </div>
      </Glass>
      {(t.paces || t.zones) && (
        <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Paces and zones">
          <header className="widget__head"><HeartPulse aria-hidden="true" /><span>Paces and heart-rate zones</span></header>
          {t.paces && (
            <div className="metrics metrics--compact">
              <div><div className="metric__value">{t.paces.easy}</div><div className="metric__label">Easy</div></div>
              <div><div className="metric__value">{t.paces.long}</div><div className="metric__label">Long</div></div>
              <div><div className="metric__value">{t.paces.tempo}</div><div className="metric__label">Tempo</div></div>
            </div>
          )}
          {t.zones && (
            <ul className="items">
              {t.zones.zones.map((z) => <li key={z.name} className="item"><span className="item__text"><span className="item__title">{z.name}</span></span><span className="muted">{z.low}–{z.high} bpm</span></li>)}
            </ul>
          )}
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>{t.zones ? `Zones from the highest heart rate your workouts recorded (${t.zones.max_hr} bpm). ` : ""}Paces from your best recent run.</p>
        </Glass>
      )}
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="The plan">
        <header className="widget__head"><Trophy aria-hidden="true" /><span>The plan · {p.race.distance_km} km{p.race.goal_time ? ` in ${p.race.goal_time}` : ""}</span></header>
        <ul className="training__weeks">
          {p.weeks.map((w) => (
            <li key={w.week_of} className={`training__week training__week--${w.kind}${w.week_of === t.this_week?.week_of ? " training__week--now" : ""}`}>
              <div className="row" style={{ justifyContent: "space-between", gap: 8 }}>
                <span className="item__title">Week of {day(w.week_of)}</span>
                <span className="muted">{w.done_km != null ? `${w.done_km} / ` : ""}{w.km} km · {w.kind === "easier" ? "easier week" : w.kind}</span>
              </div>
              <span className="career-bar" role="presentation"><span className="career-bar__fill" style={{ width: `${(w.km / peak) * 100}%` }} /></span>
              <span className="muted training__sessions">{w.sessions.map((s) => `${day(s.date).split(" ")[0]} ${s.kind === "race" ? "race" : s.km ? `${s.km} km ${s.kind}` : s.kind}${s.status === "done" ? " ✓" : s.status === "missed" ? " (missed)" : s.status === "partly" ? ` (${s.done_km} km)` : ""}`).join(" · ")}</span>
            </li>
          ))}
        </ul>
      </Glass>
    </>
  );
}

function FeedCard() {
  const [path, setPath] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => { training.feed().then((f) => setPath(f.path)).catch(() => undefined); }, []);
  const url = path ? `${window.location.origin}${path}` : "";
  const webcal = url.replace(/^https?:/, "webcal:");
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="In your calendar">
      <header className="widget__head"><CalendarPlus aria-hidden="true" /><span>In your calendar</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>Subscribe on your iPhone and each run sits next to work: tap below, or Settings → Calendar → Accounts → Add Account → Other → Add Subscribed Calendar, and paste the link. It updates as the plan changes.</p>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        {path && <a className="button button--small button--primary" href={webcal}>Subscribe</a>}
        {path && <button type="button" className="button button--small" onClick={() => { copy(url); setCopied(true); }}><Copy size={14} aria-hidden="true" /> {copied ? "Copied" : "Copy the link"}</button>}
        <button type="button" className="button button--small" onClick={async () => setPath((await training.newFeed()).path)}>New link (stops the old one)</button>
      </div>
    </Glass>
  );
}

function HealthImportCard({ health }: { health: boolean }) {
  const res = useResource<HealthImportStatus>("health:import", () => training.importStatus(), { staleMs: 60_000 });
  const [key, setKey] = useState<string | null>(null);
  const s = res.data;
  const url = `${window.location.origin}${s?.path ?? "/api/v1/health/import"}`;
  async function make() {
    if (s?.has_key && !window.confirm("A new key stops the old one: the phone will need the new one. Make a new key?")) return;
    const made = await training.newKey();
    setKey(made.key);
    res.reload(true);
  }
  const last = s?.last_ok;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Apple Health" id="health">
      <header className="widget__head"><HeartPulse aria-hidden="true" /><span>Apple Health, on its own</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>
        {last ? `Last arrived ${new Date(last.at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}${last.days?.length ? ` (${last.days.length} day${last.days.length === 1 ? "" : "s"}, to ${last.days.at(-1)})` : ""}.`
          : health ? "SirisAI has health data, but none has come through here yet." : "No health data yet."}
        {s?.last?.error ? ` The last try failed: ${s.last.error}` : ""}
      </p>
      {(s?.attempts?.length ?? 0) > 0 && (
        <details className="training__attempts" open={s!.attempts![0].status >= 400}>
          <summary>What the phone sent lately</summary>
          <ul className="items">
            {s!.attempts!.slice(0, 6).map((a) => (
              <li key={a.at + a.status} className="item">
                <span className={`item__dot ${a.status < 300 ? "dot-good" : "dot-critical"}`} aria-hidden="true" />
                <span className="item__text">
                  <span className="item__title career-wrap">{a.outcome}</span>
                  <span className="item__subtitle">{new Date(a.at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })} · {a.status}{a.bytes ? ` · ${a.bytes > 1e6 ? `${(a.bytes / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(a.bytes / 1000))} KB`}` : ""}</span>
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
      <SetupCheck />
      {s && !s.attempts?.length && s.has_key && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Nothing has reached this address yet. If the app says the export failed, check SirisOS is reachable from your phone at this address (try it in Safari), and that the server is on 5.62 or later.</p>}
      <ol className="training__steps">
        <li>Install <strong>Health Auto Export</strong> on your iPhone and allow it to read Health.</li>
        <li>In it: Automations → New → <strong>REST API</strong>. URL: <code>{url}</code> <button type="button" className="icon-link" aria-label="Copy the address" onClick={() => copy(url)}><Copy size={13} aria-hidden="true" /></button></li>
        <li>Add a header <code>Authorization</code> with <code>Bearer</code> and your key (below). Format: JSON. Aggregate: Hours (so readiness can use the HRV taken while you slept, and energy follows your day hour by hour). Period: Previous 7 Days (a sync that only sent the last few hours would undercount the day). Pick steps, active energy, exercise time, heart rate, resting heart rate, HRV, respiratory rate, sleep analysis, mindful minutes, weight, and workouts.</li>
        <li>Turn on <strong>Sync automatically</strong>. Health is locked while the phone is locked, so it sends the next time you unlock it.</li>
      </ol>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Rather use Shortcuts? A daily personal automation of "Find Health Samples" then "Get Contents of URL" (POST, JSON <code>{'{"date": "YYYY-MM-DD", "metrics": {"steps": …, "sleep_hours": …}}'}</code>) to the same address, with the same header, works too.</p>
      {key ? (
        <div className="training__key">
          <code>{key}</code>
          <button type="button" className="button button--small" onClick={() => copy(`Bearer ${key}`)}><Copy size={14} aria-hidden="true" /> Copy "Bearer …"</button>
          <p className="muted" style={{ margin: 0, fontSize: 12 }}>Shown once. SirisOS keeps only a fingerprint of it.</p>
        </div>
      ) : (
        <button type="button" className="button button--small" style={{ alignSelf: "flex-start", justifySelf: "start" }} onClick={make}>
          <KeyRound size={14} aria-hidden="true" /> {s?.has_key ? `Make a new key (now …${s.key_hint})` : "Make a key"}
        </button>
      )}
    </Glass>
  );
}

/** Is Health Auto Export set up the way SirisAI needs (6.4, SirisAI 4.03)? From what the last exports looked like. */
function SetupCheck() {
  const res = useResource<Health>("health", () => health.get(), { staleMs: 60_000, persist: true });
  const setup = res.data?.setup;
  if (!setup?.connected) return null;
  return (
    <div className="training__check" aria-label="Setup check">
      {setup.problems.length === 0 ? (
        <p className="tone-good" style={{ margin: 0, fontSize: 14 }}><CircleCheck size={14} aria-hidden="true" /> Set up right: grouped by hour, whole days, and workouts arriving.</p>
      ) : (
        <ul className="items">
          {setup.problems.map((p) => (
            <li key={p} className="item"><CircleAlert size={16} className="tone-warning" aria-hidden="true" /><span className="item__text"><span className="item__title career-wrap">{p}</span></span></li>
          ))}
        </ul>
      )}
    </div>
  );
}
