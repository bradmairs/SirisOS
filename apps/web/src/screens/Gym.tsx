import { useEffect, useMemo, useState } from "react";
import { usePageContext } from "../api/pageContext";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Activity, Mic, ArrowDown, ArrowUp, BatteryLow, Camera, CalendarDays, ChevronRight, Dumbbell, Flame, HeartPulse, ListPlus, Medal, Pencil, Play, Plus, Repeat, Ruler, Search, Settings2, Sparkles, Trash2, TrendingUp, Trophy, Upload } from "lucide-react";
import { useResource } from "../api/resource";
import { gym, loadActive, moveEntry, newId, saveActive, savePlan, type Exercise, shortcuts, type BuildEquipment, type BuildGoal, type Built, type Duplicate, type MergeDone, type ExerciseDetail, type Gym, type GymProfile, type Measurement, type Photo, type GymSettings, type ImportPreview, type ImportUnit, type Plan, type Progression, type Routine, type Session, type DayMode, type BlockChange } from "../api/gym";
import { DecimalInput } from "../components/DecimalInput";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";
import { Sheet } from "../components/Sheet";
import { BackupsCard, FitnessLine, GymCoachCard, NigglesCard, VideosCard } from "./GymCards";
import { EditExerciseSheet, ExerciseFixesCard, FixSetsForm, LinkHistoryCard, RecoveryCard, repeatWorkout } from "./GymReview";

/** SirisGym (6.5; renamed and given its importer in 6.6): start today's workout, routines, history and the exercises with your records. */
const VIEWS = [{ id: "today", label: "Today" }, { id: "routines", label: "Routines" }, { id: "history", label: "History" }, { id: "progress", label: "Progress" }, { id: "exercises", label: "Exercises" },
  { id: "settings", label: "Settings" }] as const;
type View = (typeof VIEWS)[number]["id"];
const MUSCLES = ["chest", "back", "shoulders", "biceps", "triceps", "forearms", "abs", "quads", "hamstrings", "glutes", "calves", "full body", "cardio"];
const EQUIPMENT = ["barbell", "dumbbell", "machine", "cable", "bodyweight", "kettlebell", "band", "smith", "ez bar", "trap bar", "other"];
export const fmtDay = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
export const kg = (v: number | null | undefined, unit = "kg") => (v == null ? "–" : `${Number.isInteger(v) ? v : v.toFixed(1)} ${unit}`);

export function useGym() {
  return useResource<Gym>("gym", () => gym.get(), { staleMs: 30_000, persist: true });
}

/** The reps a set starts with: last time's at the same weight, or the bottom of the range. Never the top: ticking
 * through without changing it would log reps you didn't do, and the plan would add weight because of them. */
function startingReps(e: Plan["exercises"][number], i: number, weight: number | null): number | null {
  if (e.kind !== "weight" && e.kind !== "bodyweight") return null;
  const before = e.last[i];
  if (before?.reps && (before.weight ?? null) === weight) return before.reps;
  return Number(e.reps.split("-")[0]) || null;
}

/** Start a workout: from a routine day (with last time, what to lift and warm-ups), or empty. */
export async function startWorkout(navigate: (to: string) => void, routine?: Routine, day?: number, gymId?: string, shortcut?: string, title = "Workout", mode: DayMode = "normal") {
  const now = new Date().toISOString();
  let s: Session = { id: newId(), title, started_at: now, entries: [], gym: gymId ?? null };
  if (routine) {
    const p = await gym.plan(routine.id, day, gymId, mode);
    s = { ...s, title: p.title, routine_id: routine.id, day: p.day, deload: !!p.deload, entries: p.exercises.map((e) => ({
      exercise: e.exercise,
      group: e.group ?? null,
      sets: [
        ...(e.warmups ?? []).map((w) => ({ weight: w.weight, reps: w.reps, done: false, type: "warmup" as const })),
        ...Array.from({ length: e.sets }, (_, i) => {
          const weight = e.suggest.per_set?.[i] ?? e.suggest.weight ?? e.last[i]?.weight ?? null;
          return { weight, reps: startingReps(e, i, weight), done: false, type: "normal" as const };
        }),
      ],
    })) };
    savePlan(s.id, p);
  }
  saveActive(s);
  // A Shortcut first (e.g. start the Watch's strength workout), which comes back to the workout (6.92).
  navigate("/gym/workout");
  shortcuts.run(shortcut, "/gym/workout");
}

/** What's on SirisGym, in a few lines for "Ask about this page" (7.5). */
export function gymSummary(g: Gym): string {
  const lines = [`${g.total_sessions} workouts logged, a ${g.streak_weeks}-week streak.`,
    `This week: ${g.week.sessions} workouts, ${Math.round(g.week.volume)} kg volume.`];
  if (g.readiness?.band) lines.push(`Readiness today: ${g.readiness.band}${g.readiness.score != null ? ` (${g.readiness.score})` : ""}.`);
  const under = (g.muscles ?? []).filter((m) => m.status === "under").map((m) => m.muscle);
  if (under.length) lines.push(`Under the weekly set target: ${under.join(", ")}.`);
  if (g.deload?.active) lines.push(`On a deload week until ${g.deload.until}.`);
  else if (g.deload?.suggest) lines.push(`A deload is suggested: ${g.deload.why.join("; ")}.`);
  if (g.recent[0]) lines.push(`Last workout: ${g.recent[0].title} on ${g.recent[0].date ?? ""}.`);
  return lines.join("\n");
}

export function GymScreen() {
  const res = useGym();
  const [params, setParams] = useSearchParams();
  const view = (VIEWS.find((v) => v.id === params.get("view"))?.id ?? "today") as View;
  useEffect(() => { document.title = "SirisGym · SirisOS"; }, []);
  // Recent workouts get the Watch's verdict (7.1), so what to lift and the rest timer can use it.
  useEffect(() => { gym.refreshEffort().catch(() => {}); }, []);
  const g = res.data;
  usePageContext("SirisGym", g ? gymSummary(g) : null);
  return (
    <>
      <PageHead eyebrow={g ? `${g.total_sessions} workouts · ${g.streak_weeks}-week streak` : "Gym"} title="SirisGym" />
      <div className="row career-views" role="tablist" aria-label="Gym views">
        {VIEWS.map((v) => (
          <button key={v.id} type="button" role="tab" aria-selected={view === v.id} className={`chip chip--button ${view === v.id ? "chip--active" : ""}`}
            onClick={() => setParams(v.id === "today" ? {} : { view: v.id }, { replace: true })}>{v.label}</button>
        ))}
      </div>
      {!g && res.error && <div className="error-banner" role="alert">{res.error}</div>}
      {!g && !res.error && <div className="skeleton" style={{ height: 220, marginTop: 16 }} aria-busy="true" />}
      {g && (
        <div className="stack" style={{ marginTop: 16 }}>
          {view === "today" && <TodayView g={g} onChange={() => res.reload?.(true)} />}
          {view === "routines" && <RoutinesView g={g} onChange={() => res.reload?.(true)} />}
          {view === "history" && <HistoryView g={g} onChange={() => res.reload?.(true)} />}
          {view === "progress" && <ProgressView />}
          {view === "exercises" && <ExercisesView g={g} onChange={() => res.reload?.(true)} />}
          {view === "settings" && <SettingsView g={g} onChange={() => res.reload?.(true)} />}
        </div>
      )}
    </>
  );
}

function DeloadCard({ d, onChange }: { d: NonNullable<Gym["deload"]>; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const set = async (on: boolean) => { setBusy(true); try { await gym.deload(on); onChange(); } finally { setBusy(false); } };
  const later = async () => { setBusy(true); try { await gym.deloadLater(); onChange(); } finally { setBusy(false); } };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Deload">
      <header className="widget__head"><BatteryLow aria-hidden="true" /><span>{d.active ? "Deload week" : "Time for a lighter week?"}</span></header>
      {d.active ? (
        <p style={{ margin: 0 }}>{d.planned?.this_week ? `Your planned lighter week (every ${d.planned.every} weeks), until ${fmtDay(d.until!)}` : `Until ${fmtDay(d.until!)}`}: half the sets, 10% lighter, and no records. Let your body catch up.</p>
      ) : (
        <p style={{ margin: 0 }}>{d.why.map((w) => w[0].toUpperCase() + w.slice(1)).join(". ")}. A week at half the sets and 10% lighter usually brings the numbers back up.</p>
      )}
      {!d.planned?.this_week && <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" className={`button ${d.active ? "" : "button--primary"}`} disabled={busy} onClick={() => set(!d.active)}>
          {d.active ? "End the deload" : "Start a deload week"}</button>
        {/* 8.7: it kept asking every day; "Not now" puts it away for four weeks. */}
        {!d.active && <button type="button" className="chip chip--button" disabled={busy} onClick={later}>Not now</button>}
      </div>}
    </Glass>
  );
}

/** The next block (8.8): after the routine's run its weeks, what to keep, swap or change, each one yours to accept. */
function NextBlockCard({ g, onChange }: { g: Gym; onChange: () => void }) {
  const res = useResource("gym:next-block", () => gym.nextBlock(), {});
  const b = res.data?.block;
  const [off, setOff] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const changes: BlockChange[] = b?.changes ?? [];
  const toChange = changes.map((c, i) => [c, i] as const).filter(([c]) => c.verdict !== "keep");
  const start = async () => {
    setBusy(true);
    try { const out = await gym.startBlock(toChange.filter(([, i]) => !off.has(i)).map(([, i]) => i)); setDone(`New block started${out.changed ? ` with ${out.changed} change${out.changed === 1 ? "" : "s"}` : ""}.`); onChange(); }
    finally { setBusy(false); }
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Next block">
      <header className="widget__head"><Sparkles aria-hidden="true" /><span>Time for the next block</span>{g.block && <span className="widget__source">{g.block.weeks} of {g.block.of} weeks</span>}</header>
      {done ? <p role="status" style={{ margin: 0 }}>{done}</p> : !b ? <div className="skeleton" style={{ height: 60 }} /> : (
        <>
          <p style={{ margin: 0 }}>{toChange.length ? "Here's how each lift moved this block. Untick anything you'd rather keep as it is." : "Everything's still moving: keep the routine as it is for another block."}</p>
          <ul className="items" aria-label="Changes for the next block">
            {changes.map((c, i) => (
              <li key={`${c.day}-${c.index}`} className="item">
                {c.verdict !== "keep" && <input type="checkbox" aria-label={`Change ${c.name}`} checked={!off.has(i)} onChange={() => { const n = new Set(off); if (n.has(i)) n.delete(i); else n.add(i); setOff(n); }} />}
                <span className="item__text"><span className="item__title">{c.name}{c.verdict === "swap" ? ` → ${c.swap_name}` : c.verdict === "reps" ? `: ${c.reps} → ${c.reps_to} reps` : ""}</span>
                  <span className="item__subtitle">{c.day_name} · {c.why}</span></span>
              </li>
            ))}
          </ul>
          <button type="button" className="button button--primary" style={{ alignSelf: "flex-start" }} disabled={busy} onClick={start}>Start the next block</button>
        </>
      )}
    </Glass>
  );
}

/** Working sets a month for each muscle (8.8): which are growing and which are slipping. */
function MuscleTrendsCard() {
  const [months, setMonths] = useState(12);
  const res = useResource(`gym:muscle-trends:${months}`, () => gym.muscleTrends(months), { staleMs: 60_000 });
  const d = res.data;
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Muscles over time">
      <header className="widget__head"><Activity aria-hidden="true" /><span>Muscles over time</span>
        <span className="widget__source row" style={{ gap: 6 }}>{[12, 24].map((m) => (
          <button key={m} type="button" className={`chip chip--button ${months === m ? "chip--active" : ""}`} aria-pressed={months === m} onClick={() => setMonths(m)}>{m === 12 ? "1y" : "2y"}</button>
        ))}</span></header>
      {!d ? <div className="skeleton" style={{ height: 80 }} /> : !d.muscles?.length || !d.months ? <p className="muted" style={{ margin: 0 }}>Nothing logged in that time.</p> : (
        <>
          <p className="muted" style={{ margin: 0, fontSize: 12 }}>Working sets a month; a helper muscle counts half. The % is the last 3 full months against the 3 before.</p>
          <ul className="gym-trends" aria-label="Sets a month by muscle">
            {d.muscles.map((m) => {
              // Whole months only: this one's just begun, and would always look like a drop.
              const full = m.series.slice(0, -1);
              const hi = Math.max(1, ...full);
              const pts = full.map((v, i) => `${(i / Math.max(1, full.length - 1)) * 100},${22 - (v / hi) * 20}`).join(" ");
              return (
                <li key={m.muscle}>
                  <button type="button" className="gym-trends__row" aria-expanded={open === m.muscle} onClick={() => setOpen(open === m.muscle ? null : m.muscle)}>
                    <span className="gym-trends__name">{m.muscle}</span>
                    <svg className="gym-trends__spark" viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden="true"><polyline points={pts} className="spark__line" /></svg>
                    <span className={`gym-trends__change ${m.change == null ? "muted" : m.change >= 10 ? "tone-good" : m.change <= -20 ? "tone-warning" : "muted"}`}>
                      {m.change == null ? "new" : `${m.change > 0 ? "+" : ""}${m.change}%`}</span>
                  </button>
                  {open === m.muscle && (
                    <p className="muted" style={{ margin: "2px 0 6px", fontSize: 12 }}>
                      {m.series.slice(-6).map((v, i) => `${new Date(`${d.months[d.months.length - 6 + i]}-15T12:00:00`).toLocaleDateString(undefined, { month: "short" })} ${Math.round(v)}`).join(" · ")} sets</p>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Glass>
  );
}

/** Log a set by voice (8.8): a key for an iPhone Shortcut that sends what you said to Siri. Shown once. */
function SiriCard({ has, onChange }: { has: boolean; onChange: () => void }) {
  const [key, setKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const url = `${window.location.origin}/api/v1/gym-voice/log`;
  const make = async () => {
    if (has && !window.confirm("Make a new key? The Shortcut using the old one stops working until you paste the new one in.")) return;
    setBusy(true); try { setKey((await gym.voiceKey()).key); onChange(); } finally { setBusy(false); }
  };
  const drop = async () => { if (!window.confirm("Turn off logging with Siri?")) return; setBusy(true); try { await gym.dropVoiceKey(); setKey(null); onChange(); } finally { setBusy(false); } };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Log sets with Siri">
      <header className="widget__head"><Mic aria-hidden="true" /><span>Log sets with Siri</span>{has && <span className="widget__source tone-good">On</span>}</header>
      <p style={{ margin: 0, fontSize: 14 }}>Say "Hey Siri, log a set", then "100 by 5" (or "100 kilos for 5 at RPE 8"). The set goes into the exercise you're on, next time SirisGym is open.</p>
      {key ? (
        <>
          <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 13 }}>Copy this key now: it won't be shown again.</p>
          <code className="gym-key" aria-label="Siri key">{key}</code>
          <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => void navigator.clipboard?.writeText(key)}>Copy the key</button>
        </>
      ) : null}
      <details>
        <summary style={{ fontSize: 14 }}>Make the Shortcut</summary>
        <ol style={{ margin: "6px 0 0", paddingLeft: 18, fontSize: 13 }}>
          <li>In Shortcuts, make a new one called <strong>Log a set</strong>.</li>
          <li>Add <strong>Dictate Text</strong>.</li>
          <li>Add <strong>Get Contents of URL</strong>: URL <code>{url}</code>, Method POST, Header <code>X-SirisGym-Key</code> = your key, Request Body JSON with a text field <code>text</code> set to Dictated Text.</li>
          <li>Add <strong>Get Dictionary Value</strong> for <code>say</code>, then <strong>Speak Text</strong>.</li>
        </ol>
      </details>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" className={`button ${has ? "" : "button--primary"}`} disabled={busy} onClick={make}>{has ? "Make a new key" : "Make a key"}</button>
        {has && <button type="button" className="chip chip--button" disabled={busy} onClick={drop}>Turn off</button>}
      </div>
    </Glass>
  );
}

/** Form cues for an exercise (8.8): a built-in few for the big lifts, or your own. */
function CuesEditor({ id, cues, yours, onSaved }: { id: string; cues: string; yours: boolean; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(cues);
  const save = async (v: string) => { await gym.setCues(id, v); setEditing(false); onSaved(); };
  if (editing) return (
    <div className="stack" style={{ gap: 6 }}>
      <textarea className="field" rows={3} maxLength={300} aria-label="Form cues" placeholder="e.g. Brace, knees out, chest up" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="row" style={{ gap: 8 }}>
        <button type="button" className="button button--primary" onClick={() => save(text.trim())}>Save cues</button>
        <button type="button" className="button" onClick={() => setEditing(false)}>Cancel</button>
        {yours && <button type="button" className="icon-link" style={{ marginLeft: "auto" }} onClick={() => save("")}>Back to the built-in ones</button>}
      </div>
    </div>
  );
  return (
    <p style={{ margin: 0, fontSize: 14 }}>{cues ? <><strong>Cues:</strong> {cues} </> : <span className="muted">No form cues yet. </span>}
      <button type="button" className="icon-link" onClick={() => { setText(cues); setEditing(true); }}><Pencil size={12} aria-hidden="true" /> {cues ? "Edit" : "Add"}</button></p>
  );
}

/** Protein for the day and a gym slot in the calendar (6.93). */
function FuelAndTimeCard() {
  const p = useResource("gym:protein", () => gym.protein(), { staleMs: 10 * 60_000 });
  const [slot, setSlot] = useState<{ start: string; end: string; title?: string } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fmt = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const find = async () => {
    setBusy(true); setMsg(null);
    try { const r = await gym.schedule(true); if (r.slot) setSlot({ ...r.slot, title: r.title }); else setMsg(r.detail ?? "No free time today."); }
    catch (e) { setMsg(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  const add = async () => {
    setBusy(true);
    try { await gym.schedule(false); setMsg(`Added: ${slot?.title} at ${fmt(slot!.start)}.`); setSlot(null); }
    catch (e) { setMsg(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  const d = p.data;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Protein and gym time">
      <header className="widget__head"><Activity aria-hidden="true" /><span>Protein and gym time</span></header>
      {d?.target_g ? (
        <div className="gym-protein">
          <span><strong>{d.eaten_g ?? 0} / {d.target_g} g</strong> protein <span className="muted">({d.per_kg} g/kg at {d.bodyweight} kg{d.training_day ? ", a training day" : ""})</span></span>
          <span className="gym-muscles__bar"><span className="gym-muscles__fill" style={{ width: `${Math.min(100, ((d.eaten_g ?? 0) / d.target_g) * 100)}%` }} /></span>
          {d.left_g ? <span className="muted" style={{ fontSize: 13 }}>{d.left_g} g to go. Meal photos and Apple Health's protein count towards it.</span> : <span className="tone-good" style={{ fontSize: 13 }}>Target reached.</span>}
        </div>
      ) : d && <p className="muted" style={{ margin: 0, fontSize: 13 }}>The protein target needs your weight from Apple Health.</p>}
      {slot ? (
        <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span>{slot.title}, {fmt(slot.start)}–{fmt(slot.end)}</span>
          <button type="button" className="button button--primary" disabled={busy} onClick={add}>Add to calendar</button>
          <button type="button" className="chip chip--button" onClick={() => setSlot(null)}>Not now</button>
        </div>
      ) : <button type="button" className="button" style={{ alignSelf: "flex-start" }} disabled={busy} onClick={find}><CalendarDays size={14} aria-hidden="true" /> Find gym time today</button>}
      {msg && <p role="status" className="muted" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
    </Glass>
  );
}

function TodayView({ g, onChange }: { g: Gym; onChange: () => void }) {
  const navigate = useNavigate();
  const active = loadActive();
  const routine = g.routines.find((r) => r.id === g.active?.routine);
  const next = routine?.days[g.active?.next_day ?? 0];
  const sched = g.active?.schedule ?? null;
  const todayIdx = (new Date().getDay() + 6) % 7;
  const [busy, setBusy] = useState(false);
  const [gymId, setGymId] = useState(g.settings.current_gym);
  const [mode, setMode] = useState<DayMode>("normal");
  const go = async (r?: Routine, d?: number, title?: string) => { setBusy(true); try { await startWorkout(navigate, r, d, gymId, g.settings.shortcut_start, title, mode); } finally { setBusy(false); } };
  const muscles = Object.entries(g.week.sets_by_muscle);
  const most = Math.max(1, ...muscles.map(([, n]) => n));
  return (
    <>
      {active && (
        <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Workout in progress">
          <header className="widget__head"><Dumbbell aria-hidden="true" /><span>In progress</span></header>
          <p style={{ margin: 0 }}>{active.title}, started {new Date(active.started_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}</p>
          <Link to="/gym/workout" className="button button--primary" style={{ alignSelf: "flex-start" }}>Carry on</Link>
        </Glass>
      )}
      {g.readiness?.band && g.readiness.band !== "Steady" && (
        <p className={`gym-ready gym-ready--${g.readiness.band.toLowerCase()}`} role="status">
          {g.readiness.band === "Recover" ? <BatteryLow size={14} aria-hidden="true" /> : <Activity size={14} aria-hidden="true" />}
          {g.readiness.band === "Recover" ? ` Readiness ${g.readiness.score ?? ""}: today's plan is a set lighter and 5% easier.` : ` Readiness ${g.readiness.score ?? ""}: you're primed, a good day to push.`}
        </p>
      )}
      {g.deload && (g.deload.active || g.deload.suggest) && <DeloadCard d={g.deload} onChange={onChange} />}
      {g.block?.due && <NextBlockCard g={g} onChange={onChange} />}
      {(g.niggles ?? []).length > 0 && <NigglesCard niggles={g.niggles!} onChange={onChange} />}
      {(g.links ?? 0) > 0 && <LinkHistoryCard onChange={onChange} />}
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Today's workout">
        <header className="widget__head"><Play aria-hidden="true" /><span>Today's workout</span></header>
        {g.settings.gyms.length > 1 && (
          <div className="row" role="radiogroup" aria-label="Which gym" style={{ gap: 6, flexWrap: "wrap" }}>
            {g.settings.gyms.map((x) => (
              <button key={x.id} type="button" role="radio" aria-checked={gymId === x.id} className={`chip chip--button ${gymId === x.id ? "chip--active" : ""}`}
                onClick={() => { setGymId(x.id); void gym.settings({ ...g.settings, current_gym: x.id }); }}>{x.name}</button>
            ))}
          </div>
        )}
        {routine && sched && (
          <ol className="gym-week" aria-label="This week's days">
            {sched.week.map((w, i) => (
              <li key={w.weekday} className={`${i === todayIdx ? "gym-week--today" : ""} ${w.name ? "gym-week--on" : ""}`} title={`${w.weekday}: ${w.name ?? "rest"}`}>
                <span className="gym-week__d">{w.weekday.slice(0, 3)}</span><span className="gym-week__n">{w.name ?? "Rest"}</span>
              </li>
            ))}
          </ol>
        )}
        {routine && next && sched?.rest && (
          <p style={{ margin: 0 }}>Rest day{sched.next ? `: next is ${routine.days[sched.next.day].name} on ${sched.next.weekday}.` : "."} <span className="muted">You can still train below.</span></p>
        )}
        {routine && next ? (
          <>
            <p style={{ margin: 0, fontSize: 16 }}><strong>{routine.name}: {next.name}</strong>{sched?.rest && sched.next ? <span className="muted"> ({sched.next.weekday})</span> : null}</p>
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>{next.exercises.map((e) => g.exercises.find((x) => x.id === e.exercise)?.name ?? e.exercise).join(" · ")}</p>
            {/* 8.8: how today's going, before it starts. */}
            <div className="row" role="radiogroup" aria-label="How today's going" style={{ gap: 6, flexWrap: "wrap" }}>
              {([["normal", "As planned"], ["tired", "I'm tired"], ["short", "Short on time"]] as const).map(([m, label]) => (
                <button key={m} type="button" role="radio" aria-checked={mode === m} className={`chip chip--button ${mode === m ? "chip--active" : ""}`} onClick={() => setMode(m)}>{label}</button>
              ))}
            </div>
            {mode !== "normal" && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{mode === "tired" ? "A set fewer on each exercise and 5% lighter." : "The first exercises only, the ones that matter most."}</p>}
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button type="button" className={`button ${sched?.rest ? "" : "button--primary"}`} disabled={busy || !!active} onClick={() => go(routine, g.active?.next_day)}>{sched?.rest ? `Do ${next.name} today` : `Start ${next.name}`}</button>
              {routine.days.length > 1 && routine.days.map((d, i) => i !== g.active?.next_day && (
                <button key={d.name} type="button" className="chip chip--button" disabled={busy || !!active} onClick={() => go(routine, i)}>{d.name}</button>
              ))}
            </div>
          </>
        ) : (
          <p className="muted" style={{ margin: 0 }}>No routine yet: pick a starter one under Routines, or just start an empty workout.</p>
        )}
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <button type="button" className="button" disabled={busy || !!active} onClick={() => go()}>Empty workout</button>
          <button type="button" className="button" disabled={busy || !!active} onClick={() => go(undefined, undefined, "Cardio")}><HeartPulse size={14} aria-hidden="true" /> Cardio</button>
          {g.recent[0] && (
            <button type="button" className="button" disabled={busy || !!active} title={`Again: ${g.recent[0].title}, ${fmtDay(g.recent[0].date)}`}
              onClick={async () => { setBusy(true); try { const why = await repeatWorkout(navigate, g.recent[0].id, g.settings.shortcut_start); if (why) window.alert(why); } finally { setBusy(false); } }}>
              <Repeat size={14} aria-hidden="true" /> Repeat last</button>
          )}
        </div>
      </Glass>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="This week">
        <header className="widget__head"><Flame aria-hidden="true" /><span>This week</span></header>
        <div className="metrics">
          <div><div className="metric__value">{g.week.sessions}</div><div className="metric__label">Workouts</div></div>
          <div><div className="metric__value">{Math.round(g.week.volume).toLocaleString()}</div><div className="metric__label">Volume ({g.settings.unit})</div></div>
          <div><div className="metric__value">{g.streak_weeks}</div><div className="metric__label">Weeks in a row</div></div>
          {(g.week.cardio_min ?? 0) > 0 && <div><div className="metric__value">{g.week.cardio_min}</div><div className="metric__label">Cardio min{g.week.cardio_km ? ` · ${g.week.cardio_km} km` : ""}</div></div>}
        </div>
        {g.muscles?.length ? (
          <>
            <ul className="gym-muscles" aria-label="Sets by muscle this week">
              {g.muscles.filter((m) => m.sets > 0 || g.week.sessions > 0).map((m) => {
                const top = Math.max(m.target[1] * 1.25, m.sets);
                return (
                  <li key={m.muscle} className={`gym-muscles--${m.status.replace(" ", "-")}`}>
                    <span className="gym-muscles__name">{m.muscle}</span>
                    <span className="gym-muscles__bar">
                      <span className="gym-muscles__band" style={{ left: `${(m.target[0] / top) * 100}%`, width: `${((m.target[1] - m.target[0]) / top) * 100}%` }} />
                      <span className="gym-muscles__fill" style={{ width: `${(m.sets / top) * 100}%` }} />
                    </span>
                    <span className="muted">{m.sets}</span>
                  </li>
                );
              })}
            </ul>
            {(() => {
              const under = g.muscles.filter((m) => m.status === "under" && g.week.sessions > 0).map((m) => m.muscle);
              const over = g.muscles.filter((m) => m.status === "over").map((m) => m.muscle);
              return (under.length || over.length) ? (
                <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                  {under.length ? `Under the ${g.muscles[0].target[0]}-${g.muscles[0].target[1]} sets a week: ${under.slice(0, 5).join(", ")}. ` : ""}
                  {over.length ? `Over: ${over.join(", ")}, which can outrun recovery.` : ""}
                </p>
              ) : null;
            })()}
          </>
        ) : muscles.length > 0 && (
          <ul className="gym-muscles" aria-label="Sets by muscle this week">
            {muscles.map(([m, n]) => (
              <li key={m}><span className="gym-muscles__name">{m}</span><span className="gym-muscles__bar"><span className="gym-muscles__fill" style={{ width: `${(n / most) * 100}%` }} /></span><span className="muted">{n}</span></li>
            ))}
          </ul>
        )}
      </Glass>
      {(g.recovery ?? []).length > 0 && <RecoveryCard recovery={g.recovery!} />}
      <GymCoachCard />
      {!(g.niggles ?? []).length && <NigglesCard niggles={[]} onChange={onChange} />}
      <FuelAndTimeCard />
      {(g.held ?? []).length > 0 && <HeldCard g={g} onChange={onChange} />}
      {g.recent.length > 0 && <RecentList g={g} />}
    </>
  );
}

/** Imported days too big to be one workout (7.0): nothing's deleted, and they count once you say so. */
function HeldCard({ g, onChange }: { g: Gym; onChange: () => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const decide = async (id: string, verdict: "real" | "wrong") => {
    setBusy(id);
    try { await gym.review(id, verdict); onChange(); } finally { setBusy(null); }
  };
  const held = g.held ?? [];
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Imported days to check">
      <header className="widget__head"><Activity aria-hidden="true" /><span>{held.length} imported day{held.length === 1 ? "" : "s"} to check</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Each is too big to be one workout, so an export probably put a lot of logs on one date. They're left out of your records, streak and coach until you decide. Nothing's deleted.</p>
      <ul className="items">
        {held.map((s) => (
          <li key={s.id} className="item">
            <button type="button" className="item__text house__pick" onClick={() => setOpen(s.id)}>
              <span className="item__title" style={{ whiteSpace: "normal" }}>{fmtDay(s.date)}, {s.date.slice(0, 4)}: {s.title}</span>
              <span className="item__subtitle" style={{ whiteSpace: "normal" }}>{s.sets.toLocaleString()} sets · {Math.round(s.volume).toLocaleString()} {g.settings.unit}</span>
            </button>
            <button type="button" className="chip chip--button" disabled={busy === s.id} onClick={() => decide(s.id, "real")}>It happened</button>
            <button type="button" className="chip chip--button" disabled={busy === s.id} onClick={() => decide(s.id, "wrong")}>Leave out</button>
          </li>
        ))}
      </ul>
      {open && <SessionSheet id={open} unit={g.settings.unit} onClose={() => setOpen(null)} />}
    </Glass>
  );
}

function RecentList({ g, items }: { g: Gym; items?: Gym["recent"] }) {
  const [open, setOpen] = useState<string | null>(null);
  const list = items ?? g.recent.slice(0, 5);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Recent workouts">
      <header className="widget__head"><CalendarDays aria-hidden="true" /><span>{items ? "Workouts" : "Recent"}</span>{!items && <Link to="/gym?view=history" className="widget__source">All</Link>}</header>
      {!list.length && <p className="muted" style={{ margin: 0 }}>Nothing logged yet.</p>}
      <ul className="items">
        {list.map((s) => (
          <li key={s.id} className="item">
            <button type="button" className="item__text house__pick" onClick={() => setOpen(s.id)}>
              <span className="item__title">{s.title}</span>
              <span className="item__subtitle">{fmtDay(s.date)}{s.minutes ? ` · ${s.minutes} min` : ""} · {s.sets} sets · {Math.round(s.volume).toLocaleString()} {g.settings.unit}{s.held ? " · left out of your stats" : ""}</span>
            </button>
            <ChevronRight size={16} className="muted" aria-hidden="true" />
          </li>
        ))}
      </ul>
      {open && <SessionSheet id={open} unit={g.settings.unit} onClose={() => setOpen(null)} />}
    </Glass>
  );
}

function SessionSheet({ id, unit, onClose }: { id: string; unit: string; onClose: () => void }) {
  const res = useResource(`gym:session:${id}`, () => gym.session(id), {});
  const s = res.data;
  const navigate = useNavigate();
  const [blocked, setBlocked] = useState(false);
  const again = async () => { const why = await repeatWorkout(navigate, id); if (why) setBlocked(true); else onClose(); };
  /** Correct a saved workout (7.8): it opens in the workout screen, and Save puts it back in place of the old one. */
  const edit = () => {
    if (!s) return;
    if (loadActive()) { setBlocked(true); return; }
    saveActive({ id: s.id, title: s.title, started_at: s.started_at, ended_at: s.ended_at ?? null, routine_id: s.routine_id ?? null, day: s.day ?? null,
      gym: s.gym ?? null, deload: s.deload, note: s.note ?? "", bodyweight: s.bodyweight ?? null, review: s.review,
      entries: s.entries.map(({ exercise, sets, note, group }) => ({ exercise, sets, note, group })), editing: true });
    onClose();
    navigate("/gym/workout");
  };
  return (
    <Sheet label="Workout" onClose={onClose}>
      {!s ? <div className="skeleton" style={{ height: 160 }} /> : (
        <div className="stack" style={{ gap: 10 }}>
          <h2 className="sheet__title">{s.title}</h2>
          <p className="muted" style={{ margin: 0 }}>{fmtDay(s.started_at)}{s.summary.minutes ? ` · ${s.summary.minutes} min` : ""} · {Math.round(s.summary.volume).toLocaleString()} {unit} lifted</p>
          <EffortCard id={id} />
          {s.watch && (
            <p className="gym-watch" aria-label="From your Apple Watch"><HeartPulse size={14} aria-hidden="true" />
              {[s.watch.avg_hr && `${Math.round(s.watch.avg_hr)} bpm average`, s.watch.max_hr && `${Math.round(s.watch.max_hr)} max`, s.watch.kj && `${s.watch.kj.toLocaleString()} kJ`, s.watch.minutes && `${s.watch.minutes} min on the Watch`].filter(Boolean).join(" · ")}
            </p>
          )}
          {s.deload && <p className="muted" style={{ margin: 0 }}>A deload session.</p>}
          {s.id.startsWith("import-") && (s.summary.held || s.review === "real") && (
            <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <span className="muted" style={{ fontSize: 13 }}>{s.summary.held ? "Left out of your records and stats." : "You said this one happened."}</span>
              <button type="button" className="chip chip--button" onClick={async () => { await gym.review(id, s.summary.held ? "real" : "wrong"); window.location.reload(); }}>{s.summary.held ? "It happened" : "Leave it out"}</button>
            </div>
          )}
          {s.records.length > 0 && <ul className="items">{s.records.map((r) => <li key={r.text} className="item"><Trophy size={16} className="tone-warning" aria-hidden="true" /><span className="item__text"><span className="item__title">{r.text}</span></span></li>)}</ul>}
          {s.entries.map((e) => (
            <div key={e.exercise}>
              <strong>{e.name}</strong>
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>{e.sets.filter((x) => x.done).map((x) => x.weight ? `${x.weight}×${x.reps ?? "–"}` : x.seconds ? `${x.seconds}s` : `${x.reps ?? "–"} reps`).join(", ")}</p>
            </div>
          ))}
          {blocked && <p className="tone-warning" role="alert" style={{ margin: 0, fontSize: 13 }}>Finish or discard the workout in progress first.</p>}
          <div className="row" style={{ gap: 12 }}>
            <button type="button" className="chip chip--button" onClick={again}><Repeat size={13} aria-hidden="true" /> Do this again</button>
            <button type="button" className="chip chip--button" onClick={edit}><Pencil size={13} aria-hidden="true" /> Edit</button>
            <button type="button" className="icon-link" onClick={async () => { if (window.confirm("Delete this workout?")) { await gym.deleteSession(id); onClose(); window.location.reload(); } }}>
              <Trash2 size={14} aria-hidden="true" /> Delete
            </button>
          </div>
        </div>
      )}
    </Sheet>
  );
}

function HistoryView({ g, onChange }: { g: Gym; onChange: () => void }) {
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const res = useResource(`gym:month:${month}`, () => gym.sessions(month), {});
  const days = useMemo(() => new Set((res.data?.sessions ?? []).map((s) => s.date)), [res.data]);
  const first = new Date(`${month}-01T12:00:00`);
  const lead = (first.getDay() + 6) % 7;
  const count = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  const shift = (n: number) => { const d = new Date(first); d.setMonth(d.getMonth() + n); setMonth(d.toISOString().slice(0, 7)); };
  return (
    <>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Calendar">
        <header className="widget__head"><CalendarDays aria-hidden="true" /><span>{first.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</span>
          <span className="widget__source row" style={{ gap: 6 }}><button type="button" className="chip chip--button" onClick={() => shift(-1)}>‹</button><button type="button" className="chip chip--button" onClick={() => shift(1)}>›</button></span></header>
        <div className="gym-cal" role="grid">
          {["M", "T", "W", "T", "F", "S", "S"].map((d, i) => <span key={`h${i}`} className="gym-cal__head">{d}</span>)}
          {Array.from({ length: lead }, (_, i) => <span key={`b${i}`} />)}
          {Array.from({ length: count }, (_, i) => {
            const iso = `${month}-${String(i + 1).padStart(2, "0")}`;
            return <span key={iso} className={`gym-cal__day ${days.has(iso) ? "gym-cal__day--on" : ""}`} aria-label={`${iso}${days.has(iso) ? ": worked out" : ""}`}>{i + 1}</span>;
          })}
        </div>
      </Glass>
      <RecentList g={g} items={res.data?.sessions ?? []} />
      <HeatmapCard />
      <ImportCard g={g} onDone={() => { onChange(); res.reload?.(true); }} />
    </>
  );
}

/** The last year of training, a square a day, darker for more volume (6.7). */
function HeatmapCard() {
  const res = useResource("gym:heatmap", () => gym.heatmap(), { staleMs: 60_000 });
  const days = res.data?.days ?? [];
  const by = new Map(days.map((d) => [d.date, d] as const));
  const max = Math.max(1, ...days.map((d) => d.volume));
  const today = new Date();
  const start = new Date(today);
  start.setDate(start.getDate() - 364 - ((today.getDay() + 6) % 7));
  const cells: { iso: string; level: number; title: string }[] = [];
  for (const d = new Date(start); d <= today; d.setDate(d.getDate() + 1)) {
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const x = by.get(iso);
    const level = x ? Math.min(4, 1 + Math.floor((x.volume / max) * 4)) : 0;
    cells.push({ iso, level, title: x ? `${iso}: ${x.sets} sets, ${Math.round(x.volume).toLocaleString()} kg${x.muscles.length ? ` (${x.muscles.join(", ")})` : ""}` : iso });
  }
  const weeks = new Set(days.filter((d) => d.date >= cells[0]?.iso).map((d) => d.date)).size;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="The last year">
      <header className="widget__head"><Flame aria-hidden="true" /><span>The last year</span><span className="widget__source">{weeks} day{weeks === 1 ? "" : "s"} trained</span></header>
      <div className="gym-heat" role="img" aria-label={`${weeks} day${weeks === 1 ? "" : "s"} trained in the last year`}>
        {cells.map((c) => <span key={c.iso} className={`gym-heat__day gym-heat__day--${c.level}`} title={c.title} />)}
      </div>
    </Glass>
  );
}

const HOW: Record<ImportPreview["exercises"][number]["how"], string> = { exact: "same name", close: "same exercise", guess: "best guess, check it", none: "no match" };

/** Bring years of JEFIT (or any app's CSV) in: preview, check what each exercise maps to, then import. Importing again replaces those days. */
function ImportCard({ g, onDone }: { g: Gym; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [unit, setUnit] = useState<ImportUnit>("auto");
  const [pre, setPre] = useState<ImportPreview | null>(null);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const look = async (f: File | null, u: ImportUnit) => {
    setFile(f); setPre(null); setDone(null); setError(null);
    if (!f) return;
    setBusy(true);
    try {
      const p = (await gym.importPreview(f, u)).preview;
      setPre(p);
      setChoices(Object.fromEntries(p.exercises.map((e) => [e.name, e.match ?? "new"])));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  const go = async () => {
    if (!file) return;
    setBusy(true); setError(null);
    try {
      const r = (await gym.importCommit(file, unit, choices)).imported;
      setDone(`Imported ${r.workouts.toLocaleString()} workouts and ${r.sets.toLocaleString()} sets${r.new_exercises ? `, with ${r.new_exercises} new exercises of yours` : ""}.`
        + (r.skipped_days?.length ? ` Left out ${r.skipped_days.length} day${r.skipped_days.length === 1 ? "" : "s"} already logged here.` : "")
        + (r.removed ? ` Took out ${r.removed} wrongly imported day${r.removed === 1 ? "" : "s"} (a backup was saved first).` : ""));
      setPre(null); onDone();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Import workouts">
      <header className="widget__head"><Upload aria-hidden="true" /><span>Import from JEFIT (or any CSV)</span></header>
      <p className="muted" style={{ margin: 0 }}>In JEFIT, export your data as CSV, then choose the file (or a zip of them) here. You'll see what it found before anything is saved, and importing the same export again replaces those days rather than doubling them.</p>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <input type="file" accept=".csv,.txt,.zip,text/csv,application/zip" aria-label="Export file" onChange={(e) => look(e.target.files?.[0] ?? null, unit)} />
        <label className="row" style={{ gap: 6 }}>Weights in the file
          <select className="field" value={unit} aria-label="Weights in the file" onChange={(e) => { const u = e.target.value as ImportUnit; setUnit(u); if (file) void look(file, u); }}>
            <option value="auto">as the file says (kg unless it says lb)</option><option value="kg">kg</option><option value="lb">lb (converted to kg)</option>
          </select></label>
      </div>
      {busy && <p className="muted" role="status" style={{ margin: 0 }}>Reading…</p>}
      {error && <div className="error-banner" role="alert">{error}</div>}
      {done && <p role="status" style={{ margin: 0 }}>{done}</p>}
      {pre && (
        <>
          <p role="status" style={{ margin: 0 }}><strong>{pre.workouts.toLocaleString()} workouts, {pre.sets.toLocaleString()} sets</strong>{pre.from ? `, ${fmtDay(pre.from)} ${pre.from.slice(0, 4)} to ${fmtDay(pre.to ?? pre.from)} ${(pre.to ?? pre.from).slice(0, 4)}` : ""}.
            {pre.jefit ? " Read as a JEFIT export: only your logged exercises, on their Melbourne dates." : ""}
            {pre.replacing > 0 ? ` ${pre.replacing} of those days were imported before and will be replaced.` : ""}
            {pre.removing ? ` ${pre.removing} imported day${pre.removing === 1 ? "" : "s"} that JEFIT doesn't have (from an older import) will be taken out, after a backup.` : ""}
            {pre.already_logged?.length ? ` ${pre.already_logged.length} day${pre.already_logged.length === 1 ? " is" : "s are"} already logged in SirisGym and won't be imported again (${pre.already_logged.slice(0, 3).join(", ")}${pre.already_logged.length > 3 ? "…" : ""}).` : ""}</p>
          <ul className="items" aria-label="Exercises to match">
            {pre.exercises.map((e) => (
              <li key={e.name} className="item">
                <span className="item__text"><span className="item__title">{e.name}</span>
                  <span className="item__subtitle">{e.sets} sets · {HOW[e.how]}</span></span>
                <select className="field" style={{ maxWidth: 220 }} aria-label={`${e.name} is`} value={choices[e.name] ?? "new"}
                  onChange={(ev) => setChoices({ ...choices, [e.name]: ev.target.value })}>
                  <option value="new">A new exercise of mine ({e.new_muscle})</option>
                  {g.exercises.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
                </select>
              </li>
            ))}
          </ul>
          <div className="row"><button type="button" className="button button--primary" disabled={busy} onClick={go}>Import {pre.workouts.toLocaleString()} workouts</button></div>
        </>
      )}
    </Glass>
  );
}

function RoutinesView({ g, onChange }: { g: Gym; onChange: () => void }) {
  const tpl = useResource("gym:templates", () => gym.templates(), { staleMs: 3_600_000 });
  const [editing, setEditing] = useState<Routine | null>(null);
  const names = (id: string) => g.exercises.find((x) => x.id === id)?.name ?? id;
  const copy = async (template: string) => { await gym.addRoutine({ template }); onChange(); };
  return (
    <>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Your routines">
        <header className="widget__head"><ListPlus aria-hidden="true" /><span>Your routines</span>
          <button type="button" className="widget__source icon-link" onClick={() => setEditing({ id: "", name: "", days: [{ name: "Day 1", exercises: [] }], active: g.routines.length === 0 })}><Plus size={14} aria-hidden="true" /> New</button></header>
        {!g.routines.length && <p className="muted" style={{ margin: 0 }}>None yet: copy a starter below, or make your own.</p>}
        <ul className="items">
          {g.routines.map((r) => (
            <li key={r.id} className="item">
              <button type="button" className="item__text house__pick" onClick={() => setEditing(r)}>
                <span className="item__title">{r.name}{r.active ? " · current" : ""}</span>
                <span className="item__subtitle">{r.days.map((d) => d.name).join(" · ")}</span>
              </button>
              {!r.active && <button type="button" className="chip chip--button" onClick={async () => { await gym.saveRoutine({ ...r, active: true }); onChange(); }}>Use</button>}
            </li>
          ))}
        </ul>
      </Glass>
      <BuilderCard onDraft={(r) => setEditing(r)} />
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Starter routines">
        <header className="widget__head"><Medal aria-hidden="true" /><span>Starter routines</span></header>
        <ul className="items">
          {(tpl.data?.templates ?? []).map((t) => (
            <li key={t.id} className="item">
              <span className="item__text"><span className="item__title">{t.name}</span>
                <span className="item__subtitle career-wrap">{t.note} {t.days.map((d) => `${d.name}: ${d.exercises.map((e) => names(e.exercise)).join(", ")}`).join(" · ")}</span></span>
              <button type="button" className="chip chip--button" onClick={() => copy(t.id)}>Copy</button>
            </li>
          ))}
        </ul>
      </Glass>
      {editing && <RoutineEditor g={g} start={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); onChange(); }} />}
    </>
  );
}

const AREAS = ["shoulder", "elbow", "wrist", "lower back", "knee"];

/** Build me a programme (6.9): a goal in words or picked, drafted into the routine editor to change and save. */
function BuilderCard({ onDraft }: { onDraft: (r: Routine) => void }) {
  const [text, setText] = useState("");
  const [days, setDays] = useState<number | null>(null);
  const [goal, setGoal] = useState<BuildGoal | null>(null);
  const [minutes, setMinutes] = useState<number | null>(null);
  const [equipment, setEquipment] = useState<BuildEquipment | null>(null);
  const [avoid, setAvoid] = useState<string[]>([]);
  const [built, setBuilt] = useState<Built | null>(null);
  const [busy, setBusy] = useState(false);
  const draft = async () => {
    setBusy(true);
    try {
      const b = await gym.build({ text, days, goal, minutes, equipment, avoid });
      setBuilt(b);
      onDraft(b.routine);
    } finally { setBusy(false); }
  };
  const chip = <T,>(value: T, current: T | null, set: (v: T | null) => void, label: string) => (
    <button key={label} type="button" role="radio" aria-checked={current === value} className={`chip chip--button ${current === value ? "chip--active" : ""}`}
      onClick={() => set(current === value ? null : value)}>{label}</button>
  );
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Build me a programme">
      <header className="widget__head"><Sparkles aria-hidden="true" /><span>Build me a programme</span></header>
      <textarea className="field" rows={2} aria-label="Your goal" placeholder="e.g. 4 days, hypertrophy, bad left shoulder, an hour in the gym" value={text} onChange={(e) => setText(e.target.value)} />
      <div className="row gym-chips" role="radiogroup" aria-label="Days a week">{[2, 3, 4, 5, 6].map((d) => chip(d, days, setDays, `${d} days`))}</div>
      <div className="row gym-chips" role="radiogroup" aria-label="Goal">{chip<BuildGoal>("strength", goal, setGoal, "Strength")}{chip<BuildGoal>("muscle", goal, setGoal, "Muscle")}{chip<BuildGoal>("general", goal, setGoal, "General fitness")}</div>
      <div className="row gym-chips" role="radiogroup" aria-label="Equipment">{chip<BuildEquipment>("gym", equipment, setEquipment, "A gym")}{chip<BuildEquipment>("dumbbells", equipment, setEquipment, "Dumbbells")}{chip<BuildEquipment>("bodyweight", equipment, setEquipment, "Bodyweight")}</div>
      <div className="row gym-chips" role="radiogroup" aria-label="Minutes a session">{[30, 45, 60, 75, 90].map((m) => chip(m, minutes, setMinutes, `${m} min`))}</div>
      <div className="row gym-chips" role="group" aria-label="Go easy on">
        <span className="muted" style={{ fontSize: 13 }}>Go easy on:</span>
        {AREAS.map((a) => (
          <button key={a} type="button" aria-pressed={avoid.includes(a)} className={`chip chip--button ${avoid.includes(a) ? "chip--active" : ""}`}
            onClick={() => setAvoid(avoid.includes(a) ? avoid.filter((x) => x !== a) : [...avoid, a])}>{a}</button>
        ))}
      </div>
      <button type="button" className="button button--primary" style={{ alignSelf: "flex-start" }} disabled={busy} onClick={draft}>Draft it</button>
      {built && <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>{built.note} Change anything in the editor, then save.</p>}
    </Glass>
  );
}

function RoutineEditor({ g, start, onClose, onSaved }: { g: Gym; start: Routine; onClose: () => void; onSaved: () => void }) {
  const [r, setR] = useState<Routine>(start);
  const [picking, setPicking] = useState<number | null>(null);
  const setDay = (i: number, d: Routine["days"][number]) => setR({ ...r, days: r.days.map((x, j) => (j === i ? d : x)) });
  async function save() {
    if (!r.name.trim()) return;
    if (r.id) await gym.saveRoutine(r);
    else await gym.addRoutine({ routine: { ...r, id: undefined } });
    onSaved();
  }
  return (
    <Sheet label={r.id ? "Edit routine" : "New routine"} onClose={onClose}>
      <div className="stack" style={{ gap: 10 }}>
        <h2 className="sheet__title">{r.id ? "Edit routine" : "New routine"}</h2>
        <input className="field" placeholder="Name, e.g. Push pull legs" aria-label="Routine name" value={r.name} onChange={(e) => setR({ ...r, name: e.target.value })} />
        {r.days.map((d, i) => (
          <div key={i} className="gym-day">
            <div className="row" style={{ gap: 6 }}>
              <input className="field" aria-label={`Day ${i + 1} name`} value={d.name} onChange={(e) => setDay(i, { ...d, name: e.target.value })} />
              {r.days.length > 1 && <button type="button" className="icon-link" aria-label={`Remove ${d.name}`} onClick={() => setR({ ...r, days: r.days.filter((_, j) => j !== i) })}><Trash2 size={14} aria-hidden="true" /></button>}
            </div>
            <div className="row gym-chips" role="group" aria-label={`Days for ${d.name}`}>
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((label, wd) => {
                const on = (d.weekdays ?? []).includes(wd);
                const taken = r.days.find((x, j) => j !== i && (x.weekdays ?? []).includes(wd));
                return (
                  <button key={label} type="button" aria-pressed={on} title={taken ? `${taken.name} is on ${label}` : undefined}
                    className={`chip chip--button gym-wd ${on ? "chip--active" : ""} ${taken ? "gym-wd--taken" : ""}`}
                    onClick={() => setR({ ...r, days: r.days.map((x, j) => (j === i
                      ? { ...x, weekdays: on ? (x.weekdays ?? []).filter((v) => v !== wd) : [...(x.weekdays ?? []), wd].sort() }
                      : { ...x, weekdays: (x.weekdays ?? []).filter((v) => on || v !== wd) })) })}>{label}</button>
                );
              })}
            </div>
            {d.exercises.map((e, k) => (
              <div key={`${e.exercise}-${k}`} className="row gym-plan-row">
                <span className="gym-plan-row__name">{g.exercises.find((x) => x.id === e.exercise)?.name ?? e.exercise}</span>
                <input className="field" type="number" min={1} max={20} aria-label="Sets" value={e.sets} onChange={(ev) => setDay(i, { ...d, exercises: d.exercises.map((x, j) => (j === k ? { ...x, sets: Number(ev.target.value) || 1 } : x)) })} />
                <span className="muted">×</span>
                <input className="field" aria-label="Reps" value={e.reps} onChange={(ev) => setDay(i, { ...d, exercises: d.exercises.map((x, j) => (j === k ? { ...x, reps: ev.target.value } : x)) })} />
                {/* Reorder (8.6) */}
                <button type="button" className="icon-link" disabled={k === 0} aria-label={`Move ${g.exercises.find((x) => x.id === e.exercise)?.name ?? e.exercise} up`} title="Move up"
                  onClick={() => setDay(i, { ...d, exercises: moveEntry(d.exercises, k, k - 1) })}><ArrowUp size={14} aria-hidden="true" /></button>
                <button type="button" className="icon-link" disabled={k === d.exercises.length - 1} aria-label={`Move ${g.exercises.find((x) => x.id === e.exercise)?.name ?? e.exercise} down`} title="Move down"
                  onClick={() => setDay(i, { ...d, exercises: moveEntry(d.exercises, k, k + 1) })}><ArrowDown size={14} aria-hidden="true" /></button>
                <button type="button" className="icon-link" aria-label="Remove" onClick={() => setDay(i, { ...d, exercises: d.exercises.filter((_, j) => j !== k) })}><Trash2 size={14} aria-hidden="true" /></button>
                <div className="row gym-plan-row__more">
                  <select className="field" aria-label={`How ${g.exercises.find((x) => x.id === e.exercise)?.name ?? e.exercise} progresses`} value={e.progression ?? "double"}
                    onChange={(ev) => setDay(i, { ...d, exercises: d.exercises.map((x, j) => (j === k ? { ...x, progression: ev.target.value as Progression } : x)) })}>
                    <option value="double">Top of range, then add</option><option value="linear">Add every session</option><option value="percent">% of training max</option>
                  </select>
                  {e.progression === "percent" && (
                    <input className="field" aria-label="Percent per set" placeholder="75, 80, 85" defaultValue={(e.percents ?? []).map((p) => Math.round(p * 100)).join(", ")}
                      onBlur={(ev) => setDay(i, { ...d, exercises: d.exercises.map((x, j) => (j === k ? { ...x, percents: ev.target.value.split(/[ ,]+/).map(Number).filter((n) => n > 0 && n <= 100).map((n) => n / 100) } : x)) })} />
                  )}
                  <select className="field" aria-label="Superset" value={e.group ?? ""}
                    onChange={(ev) => setDay(i, { ...d, exercises: d.exercises.map((x, j) => (j === k ? { ...x, group: ev.target.value || null } : x)) })}>
                    <option value="">On its own</option>{["A", "B", "C", "D"].map((l) => <option key={l} value={l}>Superset {l}</option>)}
                  </select>
                </div>
              </div>
            ))}
            <button type="button" className="chip chip--button" onClick={() => setPicking(i)}><Plus size={12} aria-hidden="true" /> Exercise</button>
          </div>
        ))}
        <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => setR({ ...r, days: [...r.days, { name: `Day ${r.days.length + 1}`, exercises: [] }] })}>Add a day</button>
        {/* 8.8: lighter weeks planned in, and blocks that end with a look at what's moving. */}
        <label className="gym-setting">A lighter week every
          <select className="field" value={r.deload_every ?? ""} onChange={(e) => setR({ ...r, deload_every: Number(e.target.value) || null })}>
            <option value="">None planned (SirisGym suggests one when you need it)</option>
            {[4, 5, 6, 8].map((n) => <option key={n} value={n}>{n} weeks{n === 5 ? " (4 hard, 1 light)" : ""}</option>)}
          </select></label>
        <label className="gym-setting">Block length (then SirisGym proposes the next)
          <select className="field" value={r.block_weeks ?? 6} onChange={(e) => setR({ ...r, block_weeks: Number(e.target.value) })}>
            {[4, 5, 6, 8, 10, 12].map((n) => <option key={n} value={n}>{n} weeks</option>)}
          </select></label>
        <label className="row" style={{ gap: 8, fontSize: 14 }}><input type="checkbox" checked={r.active} onChange={(e) => setR({ ...r, active: e.target.checked })} /> My current routine</label>
        <div className="row" style={{ gap: 8 }}>
          <button type="button" className="button button--primary" disabled={!r.name.trim() || !r.days.some((d) => d.exercises.length)} onClick={save}>Save</button>
          <button type="button" className="button" onClick={onClose}>Cancel</button>
          {r.id && <button type="button" className="icon-link" style={{ marginLeft: "auto" }} onClick={async () => { if (window.confirm(`Delete ${r.name}?`)) { await gym.deleteRoutine(r.id); onSaved(); } }}><Trash2 size={14} aria-hidden="true" /> Delete</button>}
        </div>
      </div>
      {picking != null && (
        <ExercisePicker exercises={g.exercises} onClose={() => setPicking(null)}
          onPick={(ex) => { const d = r.days[picking]; setDay(picking, { ...d, exercises: [...d.exercises, { exercise: ex.id, sets: 3, reps: ex.kind === "time" ? "30-60" : "8-12", rest_s: g.settings.rest_s }] }); setPicking(null); }} />
      )}
    </Sheet>
  );
}

export function ExercisePicker({ exercises, onPick, onClose }: { exercises: Exercise[]; onPick: (e: Exercise) => void; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [muscle, setMuscle] = useState("");
  const shown = exercises.filter((e) => (!muscle || e.primary === muscle) && (!q || e.name.toLowerCase().includes(q.toLowerCase())));
  return (
    <Sheet label="Pick an exercise" onClose={onClose}>
      <div className="stack" style={{ gap: 8 }}>
        <div className="row" style={{ gap: 6 }}><Search size={16} aria-hidden="true" /><input className="field" style={{ flex: 1 }} placeholder="Search exercises" aria-label="Search exercises" value={q} onChange={(e) => setQ(e.target.value)} autoFocus /></div>
        <div className="row career-views" style={{ flexWrap: "wrap" }}>
          {["", ...MUSCLES].map((m) => <button key={m || "all"} type="button" className={`chip chip--button ${muscle === m ? "chip--active" : ""}`} onClick={() => setMuscle(m)}>{m || "All"}</button>)}
        </div>
        <ul className="items gym-picker">
          {shown.map((e) => (
            <li key={e.id} className="item"><button type="button" className="item__text house__pick" onClick={() => onPick(e)}>
              <span className="item__title">{e.name}</span><span className="item__subtitle">{e.primary} · {e.equipment}{e.custom ? " · yours" : ""}</span></button></li>
          ))}
        </ul>
      </div>
    </Sheet>
  );
}

function ExercisesView({ g, onChange }: { g: Gym; onChange: () => void }) {
  const [q, setQ] = useState("");
  const [muscle, setMuscle] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const shown = g.exercises.filter((e) => (!muscle || e.primary === muscle) && (!q || e.name.toLowerCase().includes(q.toLowerCase())));
  return (
    <>
    <ExerciseFixesCard onChange={onChange} />
    <DuplicatesCard onChange={onChange} />
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Exercises">
      <header className="widget__head"><Dumbbell aria-hidden="true" /><span>{g.exercises.length} exercises</span>
        <button type="button" className="widget__source icon-link" onClick={() => setAdding(true)}><Plus size={14} aria-hidden="true" /> Your own</button></header>
      <input className="field" placeholder="Search" aria-label="Search exercises" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="row career-views" style={{ flexWrap: "wrap" }}>
        {["", ...MUSCLES].map((m) => <button key={m || "all"} type="button" className={`chip chip--button ${muscle === m ? "chip--active" : ""}`} onClick={() => setMuscle(m)}>{m || "All"}</button>)}
      </div>
      <ul className="items">
        {shown.map((e) => (
          <li key={e.id} className="item"><button type="button" className="item__text house__pick" onClick={() => setOpen(e.id)}>
            <span className="item__title">{e.name}</span><span className="item__subtitle">{e.primary}{e.secondary.length ? ` (+ ${e.secondary.join(", ")})` : ""} · {e.equipment}</span></button></li>
        ))}
      </ul>
      {open && <ExerciseSheet id={open} unit={g.settings.unit} onClose={() => setOpen(null)} onChanged={onChange} />}
      {adding && <NewExercise onClose={() => setAdding(false)} onSaved={() => { setAdding(false); onChange(); }} />}
    </Glass>
    </>
  );
}

/** Exercises that look the same (7.0): merge one into the other, and its history comes along. A copy is saved first. */
function DuplicatesCard({ onChange }: { onChange: () => void }) {
  const res = useResource("gym:duplicates", () => gym.duplicates(), { staleMs: 60_000 });
  const done = useResource("gym:merges", () => gym.merges(), { staleMs: 60_000 });
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const found = res.data?.duplicates ?? [];
  const merges = done.data?.merges ?? [];
  /** They aren't the same (8.6): not suggested again. */
  const notSame = async (d: Duplicate) => {
    setBusy(true);
    try { res.mutate?.(await gym.notSame(d.from, d.into)); setMsg(`${d.from_name} and ${d.into_name} stay apart.`); }
    catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't save that."); } finally { setBusy(false); }
  };
  /** Unmerge (8.6): the exercise and its sets come back, and the pair isn't suggested again. */
  const unmerge = async (m: MergeDone) => {
    if (!window.confirm(`Unmerge ${m.from_name} from ${m.into_name}? Its ${m.sets_moved} sets go back to it.`)) return;
    setBusy(true);
    try {
      const r = await gym.unmerge(m.id);
      setMsg(`${r.name} is back, with ${r.sets_back} sets from ${r.workouts} workouts.`);
      await Promise.all([res.reload?.(true), done.reload?.(true)]);
      onChange();
    } catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't unmerge it."); } finally { setBusy(false); }
  };
  const merge = async (d: Duplicate) => {
    if (!window.confirm(`Merge ${d.from_name} into ${d.into_name}? Its ${d.from_sets} sets move across and routines follow.`)) return;
    setBusy(true);
    try {
      const r = await gym.merge(d.from, d.into);
      setMsg(`${d.from_name} is now ${d.into_name}: ${r.sets_moved} sets from ${r.workouts} workouts moved. Undo it under Merged.`);
      await Promise.all([res.reload?.(true), done.reload?.(true)]);
      onChange();
    } catch (e) { setMsg(e instanceof Error ? e.message : "Couldn't merge them."); } finally { setBusy(false); }
  };
  if (!found.length && !merges.length && !msg) return null;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Duplicate exercises">
      <header className="widget__head"><ListPlus aria-hidden="true" /><span>{found.length ? `${found.length} that look the same` : "Duplicate exercises"}</span></header>
      <ul className="items">
        {found.map((d) => (
          <li key={d.from} className="item">
            <span className="item__text">
              <span className="item__title">{d.from_name}</span>
              <span className="item__subtitle" style={{ whiteSpace: "normal" }}>{d.from_sets} sets, into {d.into_name} ({d.into_sets} sets){d.sure ? "" : ". Check these are the same"}</span>
            </span>
            <div className="row" style={{ gap: 6, flex: "none" }}>
              <button type="button" className="chip chip--button" disabled={busy} onClick={() => merge(d)}>Merge</button>
              <button type="button" className="chip chip--button" disabled={busy} aria-label={`${d.from_name} and ${d.into_name} aren't the same`} onClick={() => notSame(d)}>Not the same</button>
            </div>
          </li>
        ))}
      </ul>
      {merges.length > 0 && (
        <details>
          <summary className="muted" style={{ fontSize: 13 }}>Merged ({merges.length})</summary>
          <ul className="items" aria-label="Merged exercises">
            {merges.map((m) => (
              <li key={m.id} className="item">
                <span className="item__text">
                  <span className="item__title">{m.from_name}</span>
                  <span className="item__subtitle">into {m.into_name} · {m.sets_moved} sets · {m.at.slice(0, 10)}</span>
                </span>
                <button type="button" className="chip chip--button" disabled={busy} aria-label={`Unmerge ${m.from_name}`} onClick={() => unmerge(m)}>Unmerge</button>
              </li>
            ))}
          </ul>
        </details>
      )}
      {msg && <p role="status" className="muted" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
    </Glass>
  );
}

function NewExercise({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ name: "", primary: "chest", secondary: [] as string[], equipment: "barbell", kind: "weight" as Exercise["kind"] });
  return (
    <Sheet label="Your own exercise" onClose={onClose}>
      <div className="stack" style={{ gap: 8 }}>
        <h2 className="sheet__title">Your own exercise</h2>
        <input className="field" placeholder="Name" aria-label="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <select className="field" aria-label="Main muscle" value={f.primary} onChange={(e) => setF({ ...f, primary: e.target.value })}>{MUSCLES.map((m) => <option key={m}>{m}</option>)}</select>
        <select className="field" aria-label="Equipment" value={f.equipment} onChange={(e) => setF({ ...f, equipment: e.target.value })}>{EQUIPMENT.map((m) => <option key={m}>{m}</option>)}</select>
        <select className="field" aria-label="Logged as" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value as Exercise["kind"] })}>
          <option value="weight">Weight × reps</option><option value="bodyweight">Reps (bodyweight)</option><option value="time">Time</option><option value="cardio">Cardio (time and distance)</option>
        </select>
        <div className="row" style={{ gap: 8 }}>
          <button type="button" className="button button--primary" disabled={!f.name.trim()} onClick={async () => { await gym.addExercise(f); onSaved(); }}>Save</button>
          <button type="button" className="button" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </Sheet>
  );
}

/** One exercise: records, a chart of estimated 1RM, and every time you've done it. */
export function ExerciseSheet({ id, unit, onClose, onChanged }: { id: string; unit: string; onClose: () => void; onChanged?: () => void }) {
  const res = useResource<ExerciseDetail>(`gym:exercise:${id}`, () => gym.exercise(id), {});
  const d = res.data;
  const [fixing, setFixing] = useState<string | null>(null);  // a workout whose sets of this are being corrected (8.7)
  const [editing, setEditing] = useState(false);
  // A set far above the rest is likely a typo (8.7): it gets a mark, and Fix.
  const typical = d ? [...d.history.map((h) => h.e1rm ?? 0)].filter(Boolean).sort((a, b) => a - b)[Math.floor(d.history.filter((h) => h.e1rm).length / 2)] ?? 0 : 0;
  return (
    <Sheet label="Exercise" onClose={onClose}>
      {!d ? <div className="skeleton" style={{ height: 160 }} /> : (
        <div className="stack" style={{ gap: 10 }}>
          <h2 className="sheet__title">{d.exercise.name}</h2>
          <p className="muted" style={{ margin: 0 }}>{d.exercise.primary}{d.exercise.secondary.length ? `, with ${d.exercise.secondary.join(", ")}` : ""} · {d.exercise.equipment}
            {d.exercise.custom && <> · <button type="button" className="icon-link" onClick={() => setEditing(true)}><Pencil size={12} aria-hidden="true" /> Edit</button></>}</p>
          <CuesEditor key={d.cues ?? ""} id={id} cues={d.cues ?? ""} yours={!!d.cues_yours} onSaved={() => res.reload?.(true)} />
          {editing && <EditExerciseSheet exercise={d.exercise} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); void res.reload?.(true); onChanged?.(); }} />}
          {!d.history.length && <p className="muted" style={{ margin: 0 }}>Not done yet.</p>}
          {d.history.length > 0 && (
            <>
              <div className="metrics">
                <div><div className="metric__value">{kg(d.records.e1rm?.value, unit)}</div><div className="metric__label">Best est. 1RM</div></div>
                <div><div className="metric__value">{kg(d.records.heaviest?.weight, unit)}</div><div className="metric__label">Heaviest</div></div>
                <div><div className="metric__value">{d.records.best_volume ? Math.round(d.records.best_volume.volume).toLocaleString() : "–"}</div><div className="metric__label">Biggest session</div></div>
              </div>
              {d.records.rep_max && Object.keys(d.records.rep_max).length > 0 && (
                <p className="muted" style={{ margin: 0, fontSize: 13 }}>Best for: {Object.entries(d.records.rep_max).map(([n, r]) => `${n} rep${n === "1" ? "" : "s"} ${kg(r.weight, unit)}`).join(" · ")}</p>
              )}
              <E1rmChart series={d.series} />
              {d.fitness && <FitnessLine f={d.fitness} />}
              <ul className="items" aria-label="History">
                {d.history.map((h) => {
                  const odd = !!typical && !!h.e1rm && h.e1rm > typical * 1.6;
                  return (
                    <li key={h.session} className="item gym-history">
                      <span className="item__text"><span className="item__title">{fmtDay(h.date)}{odd && <span className="tone-warning" style={{ fontSize: 12 }}> · looks like a typo</span>}</span>
                        <span className="item__subtitle">{h.sets.map((x) => (x.weight ? `${x.weight}×${x.reps ?? "–"}` : x.seconds ? `${x.seconds}s` : `${x.reps ?? "–"}`)).join(", ")}{h.e1rm ? ` · est. 1RM ${h.e1rm}` : ""}</span>
                        {fixing === h.session && <FixSetsForm session={h.session} exercise={id} sets={h.sets} onCancel={() => setFixing(null)}
                          onDone={() => { setFixing(null); void res.reload?.(true); onChanged?.(); }} />}
                      </span>
                      {fixing !== h.session && <button type="button" className={`chip chip--button ${odd ? "chip--active" : ""}`} aria-label={`Fix the sets on ${fmtDay(h.date)}`} onClick={() => setFixing(h.session)}>Fix</button>}
                    </li>
                  );
                })}
              </ul>
            </>
          )}
          <h3 style={{ margin: "8px 0 0", fontSize: 15 }}>Form videos</h3>
          <VideosCard key={(d.videos ?? []).map((v) => v.id).join()} videos={d.videos ?? []} onChange={() => res.reload?.(true)} />
        </div>
      )}
    </Sheet>
  );
}

function E1rmChart({ series }: { series: ExerciseDetail["series"] }) {
  const pts = series.map((p, i) => ({ i, y: p.e1rm ?? p.best })).filter((p): p is { i: number; y: number } => p.y != null);
  if (pts.length < 2) return null;
  const lo = Math.min(...pts.map((p) => p.y)), hi = Math.max(...pts.map((p) => p.y));
  const W = 300, H = 80, pad = (hi - lo) * 0.15 || 1;
  const x = (i: number) => (i / (series.length - 1)) * W;
  const y = (v: number) => H - ((v - lo + pad) / (hi - lo + 2 * pad)) * H;
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={`Estimated 1RM from ${lo} to ${hi}`}>
      <polyline points={pts.map((p) => `${x(p.i)},${y(p.y)}`).join(" ")} className="spark__line" />
      {pts.map((p) => <circle key={p.i} cx={x(p.i)} cy={y(p.y)} r={2.5} className="spark__dot" />)}
    </svg>
  );
}

const list = (v: string) => v.split(/[ ,]+/).map(Number).filter((n) => Number.isFinite(n) && n > 0);

/** SirisGym's settings (6.7): rest, the weight step, warm-ups, and each gym with its bar, plates, dumbbells and machines. */
function SettingsView({ g, onChange }: { g: Gym; onChange: () => void }) {
  const [s, setS] = useState<GymSettings>(g.settings);
  const [saved, setSaved] = useState(false);
  const setGym = (id: string, patch: Partial<GymProfile>) => setS({ ...s, gyms: s.gyms.map((x) => (x.id === id ? { ...x, ...patch } : x)) });
  const save = async () => { setSaved(false); setS(await gym.settings(s)); setSaved(true); onChange(); };
  return (
    <>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Training settings">
        <header className="widget__head"><Settings2 aria-hidden="true" /><span>Training</span></header>
        <label className="gym-setting">Rest between sets (s)<input className="field" type="number" min={0} max={900} value={s.rest_s} onChange={(e) => setS({ ...s, rest_s: Number(e.target.value) || 0 })} /></label>
        <label className="gym-setting">Rest between exercises (s)<input className="field" type="number" min={0} max={900} value={s.rest_between_s ?? 120} onChange={(e) => setS({ ...s, rest_between_s: Number(e.target.value) || 0 })} /></label>
        <label className="gym-setting">Weight step (kg)<input className="field" type="number" step={0.25} min={0.25} max={20} value={s.increment} onChange={(e) => setS({ ...s, increment: Number(e.target.value) || 2.5 })} /></label>
        <label className="gym-setting">iPhone Shortcut to run when a workout starts
          <input className="field" placeholder="e.g. SirisGym Start (empty: none)" value={s.shortcut_start ?? ""} onChange={(e) => setS({ ...s, shortcut_start: e.target.value })} /></label>
        <label className="gym-setting">…and when it finishes or is discarded (to stop the Watch workout)
          <input className="field" placeholder="e.g. SirisGym Finish (empty: none)" value={s.shortcut_finish ?? ""} onChange={(e) => setS({ ...s, shortcut_finish: e.target.value })} /></label>
        {!!s.shortcut_start?.trim() && !s.shortcut_finish?.trim() && (
          <p className="tone-warning" role="status" style={{ margin: 0, fontSize: 12 }}>With a start Shortcut but no finish one, the Watch workout keeps running after you finish or discard here. Name a Shortcut that ends it.</p>
        )}
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>Make the Shortcut in the Shortcuts app with this exact name, e.g. one that starts a Traditional Strength Training workout on your Watch, so heart rate and kJ are recorded and matched to the session. The finish one gets "finished" or "discarded" as its input, and should end the Watch workout. It runs on iPhone. In Safari it comes straight back; from the Home Screen app, tap ◀ SirisOS at the top left (a link back would open Safari instead, without your workout).</p>
        <label className="gym-setting">…and for each rest, given its seconds (e.g. to start a Clock timer, which shows on the lock screen and Dynamic Island)
          <input className="field" placeholder="e.g. SirisGym Rest (empty: none)" value={s.shortcut_rest ?? ""} onChange={(e) => setS({ ...s, shortcut_rest: e.target.value })} /></label>
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>A web app can't put up a Live Activity itself; only iPhone apps can. A Clock timer can: make a Shortcut that takes the input as seconds and runs Start Timer. Each rest then opens Shortcuts for a moment; from the Home Screen app, tap ◀ SirisOS at the top left to come back.</p>
        <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={s.learn_rest ?? true} onChange={(e) => setS({ ...s, learn_rest: e.target.checked })} /> Set the rest timer from how long my heart rate takes to settle (needs the Watch)</label>
        <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={s.keep_awake ?? true} onChange={(e) => setS({ ...s, keep_awake: e.target.checked })} /> Keep the screen on during a workout</label>
        <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={s.warmups} onChange={(e) => setS({ ...s, warmups: e.target.checked })} /> Add warm-up sets before the first lift for each muscle</label>
        {s.warmups && (
          <label className="gym-setting">Warm-ups (% of the working weight × reps)
            <input className="field" aria-label="Warm-up steps" defaultValue={s.warmup_steps.map((w) => `${Math.round(w.percent * 100)}x${w.reps}`).join(", ")}
              onBlur={(e) => setS({ ...s, warmup_steps: e.target.value.split(/[ ,]+/).map((t) => t.split(/x|×/)).filter((p) => p.length === 2 && Number(p[0]) > 0 && Number(p[1]) > 0)
                .map(([p, r]) => ({ percent: Math.min(1, Number(p) / 100), reps: Number(r) })) })} />
          </label>
        )}
      </Glass>
      {s.gyms.map((x) => (
        <Glass key={x.id} as="section" className="widget" style={{ minHeight: 0 }} aria-label={`Gym: ${x.name}`}>
          <header className="widget__head"><Dumbbell aria-hidden="true" /><span>{x.name}{x.id === s.current_gym ? " · current" : ""}</span>
            {s.gyms.length > 1 && <button type="button" className="widget__source icon-link" aria-label={`Remove ${x.name}`}
              onClick={() => setS({ ...s, gyms: s.gyms.filter((y) => y.id !== x.id), current_gym: s.current_gym === x.id ? s.gyms.find((y) => y.id !== x.id)!.id : s.current_gym })}><Trash2 size={14} aria-hidden="true" /></button>}</header>
          <label className="gym-setting">Name<input className="field" value={x.name} onChange={(e) => setGym(x.id, { name: e.target.value })} /></label>
          <label className="gym-setting">Bar (kg)<input className="field" type="number" step={0.5} value={x.bar} onChange={(e) => setGym(x.id, { bar: Number(e.target.value) || 0 })} /></label>
          <label className="gym-setting">Plates (kg, one of each pair)<input className="field" defaultValue={x.plates.join(", ")} onBlur={(e) => setGym(x.id, { plates: list(e.target.value) })} /></label>
          <label className="gym-setting">Dumbbells on the rack (kg; empty for any)<input className="field" defaultValue={x.dumbbells.join(", ")} placeholder="2.5, 5, 7.5, 10 …" onBlur={(e) => setGym(x.id, { dumbbells: list(e.target.value) })} /></label>
          <label className="gym-setting">Machine stack step (kg)<input className="field" type="number" step={0.5} value={x.stack_step ?? ""} placeholder="any" onChange={(e) => setGym(x.id, { stack_step: Number(e.target.value) || null })} /></label>
          {x.id !== s.current_gym && <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => setS({ ...s, current_gym: x.id })}>Train here now</button>}
        </Glass>
      ))}
      <SiriCard has={!!g.settings.voice_key} onChange={onChange} />
      <TidyCard onChange={onChange} />
      <BackupsCard onChange={onChange} />
      <div className="row" style={{ gap: 8 }}>
        <button type="button" className="button" onClick={() => setS({ ...s, gyms: [...s.gyms, { id: newId(), name: `Gym ${s.gyms.length + 1}`, bar: 20, plates: [25, 20, 15, 10, 5, 2.5, 1.25], dumbbells: [], stack_step: null }] })}>
          <Plus size={14} aria-hidden="true" /> Add a gym</button>
        <button type="button" className="button button--primary" onClick={save}>Save settings</button>
        {saved && <span role="status" className="muted">Saved.</span>}
      </div>
    </>
  );
}

const LEVEL_TONE: Record<string, string> = { "starting out": "", beginner: "", novice: "tone-good", intermediate: "tone-good", advanced: "tone-warning" };

/** Strength against bodyweight and the year in review (6.8). */
/** Body measurements against your weight (6.9). */
function BodyCard() {
  const res = useResource("gym:body", () => gym.body(), { staleMs: 60_000 });
  const today = new Date().toISOString().slice(0, 10);
  const [m, setM] = useState<Measurement>({ date: today });
  const [adding, setAdding] = useState(false);
  const b = res.data;
  const keys: [keyof Measurement, string][] = [["waist", "Waist"], ["chest", "Chest"], ["hips", "Hips"], ["arm", "Arm"], ["thigh", "Thigh"], ["calf", "Calf"], ["neck", "Neck"]];
  const ms = b?.measurements ?? [];
  const first = ms[0], last = ms[ms.length - 1];
  const w = b?.weight ?? [];
  const spark = (() => {
    if (w.length < 2) return null;
    const vals = w.map((x) => x.trend ?? x.kg), lo = Math.min(...vals), hi = Math.max(...vals), span = Math.max(0.5, hi - lo);
    return vals.map((v, i) => `${(i / (vals.length - 1)) * 100},${30 - ((v - lo) / span) * 28}`).join(" ");
  })();
  const save = async () => { await gym.addMeasurement(m); setAdding(false); setM({ date: today }); res.reload?.(true); };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Body">
      <header className="widget__head"><Ruler aria-hidden="true" /><span>Body</span>
        <button type="button" className="widget__source icon-link" onClick={() => setAdding(!adding)}><Plus size={14} aria-hidden="true" /> Measure</button></header>
      {w.length > 0 && (
        <div className="gym-weight">
          <span><strong>{w[w.length - 1].kg.toFixed(1)} kg</strong> <span className="muted">from Apple Health{w.length > 1 && w[w.length - 1].trend ? `, trend ${w[w.length - 1].trend.toFixed(1)} kg` : ""}</span></span>
          {spark && <svg viewBox="0 0 100 32" preserveAspectRatio="none" className="gym-weight__line" role="img" aria-label="Weight trend"><polyline points={spark} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" /></svg>}
        </div>
      )}
      {adding && (
        <div className="gym-measure">
          <label className="gym-setting">Date<input className="field" type="date" value={m.date} onChange={(e) => setM({ ...m, date: e.target.value })} /></label>
          {keys.map(([k, label]) => (
            <label key={k} className="gym-setting">{label} (cm)<DecimalInput className="field" aria-label={`${label} (cm)`} value={m[k] as number | null | undefined}
              onValue={(v) => setM({ ...m, [k]: v })} /></label>
          ))}
          <button type="button" className="button button--primary" onClick={save}>Save measurements</button>
        </div>
      )}
      {last ? (
        <ul className="items" aria-label="Measurements">
          {keys.filter(([k]) => last[k] != null).map(([k, label]) => {
            const from = ms.find((x) => x[k] != null)?.[k] as number | undefined;
            const d = from != null && first !== last ? Math.round(((last[k] as number) - from) * 10) / 10 : null;
            return <li key={k} className="item"><span className="item__text"><span className="item__title">{label}: {last[k] as number} cm</span>
              {d ? <span className="item__subtitle">{d > 0 ? "+" : ""}{d} cm since {fmtDay(ms.find((x) => x[k] != null)!.date)}</span> : null}</span></li>;
          })}
        </ul>
      ) : !adding && <p className="muted" style={{ margin: 0 }}>No measurements yet. Waist, chest and arms once a month is plenty.</p>}
    </Glass>
  );
}

/** Progress photos (6.9): kept on your server only; compare two dates side by side. */
function PhotosCard() {
  const res = useResource("gym:body", () => gym.body(), { staleMs: 60_000 });
  const photos = res.data?.photos ?? [];
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [pose, setPose] = useState<Photo["pose"]>("front");
  const [busy, setBusy] = useState(false);
  const [pair, setPair] = useState<[string | null, string | null]>([null, null]);
  useEffect(() => {
    let alive = true;
    for (const p of photos) if (!urls[p.id]) gym.photoUrl(p.id).then((u) => { if (alive) setUrls((x) => ({ ...x, [p.id]: u })); }).catch(() => {});
    return () => { alive = false; };
  }, [photos.map((p) => p.id).join()]);  // eslint-disable-line react-hooks/exhaustive-deps
  const shown = photos.filter((p) => p.pose === pose);
  const a = pair[0] ?? shown[0]?.id ?? null, b = pair[1] ?? shown[shown.length - 1]?.id ?? null;
  const up = async (f: File | undefined) => {
    if (!f) return;
    setBusy(true);
    try { await gym.addPhoto(f, new Date().toISOString().slice(0, 10), pose); res.reload?.(true); } finally { setBusy(false); }
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Progress photos">
      <header className="widget__head"><Camera aria-hidden="true" /><span>Progress photos</span><span className="widget__source">only on your server</span></header>
      <div className="row gym-chips" role="radiogroup" aria-label="Pose">
        {(["front", "side", "back"] as const).map((p) => <button key={p} type="button" role="radio" aria-checked={pose === p} className={`chip chip--button ${pose === p ? "chip--active" : ""}`} onClick={() => { setPose(p); setPair([null, null]); }}>{p}</button>)}
      </div>
      {shown.length >= 2 && a && b && (
        <div className="gym-compare">
          {[a, b].map((id, i) => {
            const p = shown.find((x) => x.id === id)!;
            return (
              <figure key={i}>
                {urls[id] ? <img src={urls[id]} alt={`${p.pose}, ${p.date}`} /> : <div className="skeleton" style={{ aspectRatio: "3/4" }} />}
                <select className="field" aria-label={i === 0 ? "Before" : "After"} value={id} onChange={(e) => setPair(i === 0 ? [e.target.value, pair[1]] : [pair[0], e.target.value])}>
                  {shown.map((x) => <option key={x.id} value={x.id}>{x.date}</option>)}
                </select>
              </figure>
            );
          })}
        </div>
      )}
      {shown.length === 1 && urls[shown[0].id] && <img className="gym-photo-one" src={urls[shown[0].id]} alt={`${pose}, ${shown[0].date}`} />}
      {!shown.length && <p className="muted" style={{ margin: 0 }}>No {pose} photos yet. Same spot, light and time of day each month makes them comparable.</p>}
      <label className="button" style={{ alignSelf: "flex-start" }} aria-disabled={busy}>
        <Camera size={14} aria-hidden="true" /> {busy ? "Saving…" : `Add a ${pose} photo`}
        <input type="file" accept="image/*" capture="user" hidden onChange={(e) => up(e.target.files?.[0])} aria-label={`Add a ${pose} photo`} />
      </label>
      {shown.length > 0 && (
        <button type="button" className="icon-link" style={{ alignSelf: "flex-start" }} onClick={async () => { if (b && window.confirm("Delete this photo?")) { await gym.deletePhoto(b); setPair([null, null]); res.reload?.(true); } }}>
          <Trash2 size={14} aria-hidden="true" /> {shown.length >= 2 ? "Delete the right-hand photo" : "Delete the photo"}</button>
      )}
    </Glass>
  );
}

function ProgressView() {
  const st = useResource("gym:strength", () => gym.strength(), { staleMs: 60_000 });
  const [y, setY] = useState(() => new Date().getFullYear());
  const yr = useResource(`gym:year:${y}`, () => gym.year(y), { staleMs: 60_000 });
  const r = yr.data;
  const maxVol = Math.max(1, ...(r?.months ?? []).map((m) => m.volume));
  const delta = (a: number, b: number) => (b ? `${a >= b ? "+" : ""}${Math.round(((a - b) / b) * 100)}%` : "");
  return (
    <>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Strength">
        <header className="widget__head"><TrendingUp aria-hidden="true" /><span>Strength</span>{st.data?.bodyweight && <span className="widget__source">at {st.data.bodyweight} kg</span>}</header>
        {!st.data?.lifts.length && <p className="muted" style={{ margin: 0 }}>Log a squat, bench, deadlift, overhead press, row or pull-up to see where you stand.</p>}
        <ul className="items">
          {(st.data?.lifts ?? []).map((l) => (
            <li key={l.exercise} className="item">
              <span className="item__text"><span className="item__title">{l.name}: {l.best} kg</span>
                <span className="item__subtitle career-wrap">est. 1RM, {fmtDay(l.date)} {l.date.slice(0, 4)}{l.last_year && l.this_year ? ` · this year ${l.this_year} (${delta(l.this_year, l.last_year)} on last year)` : ""}</span></span>
              {l.ratio != null && <span className={`gym-level ${LEVEL_TONE[l.level ?? ""] ?? ""}`}>{l.exercise === "pull-up" ? `+${l.ratio}` : l.ratio}× bw<br /><span className="muted">{l.level}</span></span>}
            </li>
          ))}
        </ul>
        {st.data && !st.data.bodyweight && <p className="muted" style={{ margin: 0, fontSize: 13 }}>No bodyweight yet: it comes from Apple Health (weight), so the ratios appear once one arrives.</p>}
      </Glass>
      <MuscleTrendsCard />
      <BodyCard />
      <PhotosCard />
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Year in review">
        <header className="widget__head"><CalendarDays aria-hidden="true" /><span>{y} in the gym</span>
          <span className="widget__source row" style={{ gap: 6 }}><button type="button" className="chip chip--button" aria-label="The year before" onClick={() => setY(y - 1)}>‹</button>
            <button type="button" className="chip chip--button" aria-label="The year after" disabled={y >= new Date().getFullYear()} onClick={() => setY(y + 1)}>›</button></span></header>
        {r && (
          <>
            <div className="metrics">
              <div><div className="metric__value">{r.sessions}</div><div className="metric__label">Workouts {delta(r.sessions, r.previous.sessions)}</div></div>
              <div><div className="metric__value">{r.hours}</div><div className="metric__label">Hours</div></div>
              <div><div className="metric__value">{(r.volume / 1000).toFixed(r.volume >= 100000 ? 0 : 1)} t</div><div className="metric__label">Lifted {delta(r.volume, r.previous.volume)}</div></div>
            </div>
            <div className="gym-months" role="img" aria-label="Volume by month">
              {r.months.map((m) => (
                <span key={m.month} className="gym-months__col" title={`${m.month}: ${m.sessions} workouts, ${Math.round(m.volume).toLocaleString()} kg, ${m.records} records`}>
                  <span className="gym-months__bar" style={{ height: `${(m.volume / maxVol) * 100}%` }} />
                  {m.records > 0 && <Trophy size={10} className="tone-warning" aria-hidden="true" />}
                  <span className="gym-months__label">{new Date(`${m.month}-15T12:00:00`).toLocaleDateString(undefined, { month: "narrow" })}</span>
                </span>
              ))}
            </div>
            {r.best.length > 0 && <p style={{ margin: 0, fontSize: 14 }}>Best lifts: {r.best.map((b) => `${b.name} ${b.e1rm} kg`).join(" · ")}</p>}
            {r.muscles.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Most trained: {r.muscles.map((m) => m.muscle).join(", ")}.</p>}
          </>
        )}
      </Glass>
    </>
  );
}


/** Exercises with nothing logged (6.95): see which, then take them out. Workouts are kept, and a copy is saved first. */
function TidyCard({ onChange }: { onChange: () => void }) {
  const [found, setFound] = useState<{ names: string[]; entries_removed: number } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const look = async () => { setMsg(null); setFound(await gym.cleanup(true)); };
  const go = async () => {
    const r = await gym.cleanup(false);
    setFound(null);
    setMsg(`Took out ${r.exercises_removed} exercise${r.exercises_removed === 1 ? "" : "s"} and ${r.entries_removed} empty entr${r.entries_removed === 1 ? "y" : "ies"}; all ${r.sessions_kept} workouts kept.`);
    onChange();
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Tidy up">
      <header className="widget__head"><Trash2 aria-hidden="true" /><span>Exercises with nothing logged</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Your own exercises with no sets anywhere and not in a routine, and empty entries in workouts. Workouts themselves are never removed.</p>
      {found ? (
        found.names.length || found.entries_removed ? (
          <>
            <p style={{ margin: 0, fontSize: 14 }}>{found.names.length ? found.names.join(", ") : "No exercises"}{found.entries_removed ? ` and ${found.entries_removed} empty entries` : ""}.</p>
            <button type="button" className="button button--primary" style={{ alignSelf: "flex-start" }} onClick={go}>Take them out</button>
          </>
        ) : <p className="muted" style={{ margin: 0 }}>Nothing to tidy.</p>
      ) : <button type="button" className="button" style={{ alignSelf: "flex-start" }} onClick={look}>Look for them</button>}
      {msg && <p role="status" style={{ margin: 0 }}>{msg}</p>}
    </Glass>
  );
}

/** The Watch's heart rate lined up with each set (6.96): the effort per exercise, worked out by SirisAI. */
function EffortCard({ id }: { id: string }) {
  const res = useResource(`gym:effort:${id}`, () => gym.effort(id), {});
  const e = res.data;
  if (!e) return null;
  if (!e.linked) return <p className="muted" style={{ margin: 0, fontSize: 13 }}><HeartPulse size={13} aria-hidden="true" /> {e.why}</p>;
  const tl = e.timeline ?? [];
  const t0 = tl.length ? new Date(tl[0][0]).getTime() : 0, t1 = tl.length ? new Date(tl[tl.length - 1][0]).getTime() + 60_000 : 1;
  const lo = Math.min(...tl.map((p) => p[1]), 60), hi = Math.max(...tl.map((p) => p[2]), lo + 20);
  const x = (iso: string) => ((new Date(iso).getTime() - t0) / (t1 - t0)) * 100;
  const y = (v: number) => 40 - ((v - lo) / (hi - lo)) * 38;
  const names = [...new Set((e.sets ?? []).map((s) => s.exercise))];
  return (
    <section className="gym-effort" aria-label="Effort">
      <h3 className="gym-effort__title"><HeartPulse size={14} aria-hidden="true" /> Effort, from your Watch</h3>
      {tl.length > 1 && (
        <svg viewBox="0 0 100 42" preserveAspectRatio="none" className="gym-effort__chart" role="img" aria-label="Heart rate through the workout, with each set marked">
          {(e.sets ?? []).filter((s) => s.type !== "warmup").map((s, i) => (
            <rect key={i} x={x(s.at) - 1.2} y={0} width={2.4} height={42} className={`gym-effort__set gym-effort__set--${names.indexOf(s.exercise) % 4}`} />
          ))}
          <polyline points={tl.map((p) => `${x(p[0])},${y(p[1])}`).join(" ")} fill="none" stroke="currentColor" strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
        </svg>
      )}
      {e.text && <p style={{ margin: 0, fontSize: 14 }}>{e.text}</p>}
      {(e.advice ?? []).length > 0 && (
        <ul className="gym-advice" aria-label="For next time">
          {e.advice!.map((a) => <li key={a}>{a}</li>)}
        </ul>
      )}
      {(e.exercises ?? []).length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table className="health-sources">
            <thead><tr><th>Exercise</th><th>Effort</th><th>Peak</th><th>Recovery</th><th>Est. 1RM</th></tr></thead>
            <tbody>
              {e.exercises!.map((x2) => (
                <tr key={x2.exercise}>
                  <td><span className={`gym-effort__dot gym-effort__set--${names.indexOf(x2.exercise) % 4}`} />{x2.exercise}</td>
                  <td>{x2.effort != null ? `${x2.effort}/10` : "–"}{x2.rpe ? <span className="muted"> (RPE {x2.rpe})</span> : null}</td>
                  <td>{x2.peak_hr ? `${x2.peak_hr} bpm` : "–"}{x2.peak_share ? <span className="muted"> {Math.round(x2.peak_share * 100)}%</span> : null}</td>
                  <td>{x2.recovery_bpm != null ? `−${x2.recovery_bpm} bpm` : "–"}</td>
                  <td>{x2.e1rm ? `${x2.e1rm} kg` : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>{[e.avg_hr && `${e.avg_hr} bpm average`, e.peak_hr && `${e.peak_hr} peak`, e.kj && `${e.kj.toLocaleString()} kJ`, e.watch?.name].filter(Boolean).join(" · ")}</p>
    </section>
  );
}
