import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity, BatteryLow, CalendarDays, ChevronRight, Dumbbell, Flame, HeartPulse, Pencil, Play, Repeat, Sparkles, Trash2, Trophy } from "lucide-react";
import { useResource } from "../api/resource";
import { gym, loadActive, saveActive, type Gym, type Routine, type DayMode, type BlockChange } from "../api/gym";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";
import { GymCoachCard, NigglesCard } from "./GymCards";
import { LinkHistoryCard, RecoveryCard, repeatWorkout } from "./GymReview";
import { EffortCard } from "./GymExercises";
import { fmtDay, startWorkout } from "./GymShared";

/** SirisGym's Today tab (split out of Gym.tsx in 8.9). */

export function DeloadCard({ d, onChange }: { d: NonNullable<Gym["deload"]>; onChange: () => void }) {
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
export function NextBlockCard({ g, onChange }: { g: Gym; onChange: () => void }) {
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

/** Protein for the day and a gym slot in the calendar (6.93). */
export function FuelAndTimeCard() {
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

export function TodayView({ g, onChange }: { g: Gym; onChange: () => void }) {
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
export function HeldCard({ g, onChange }: { g: Gym; onChange: () => void }) {
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

export function RecentList({ g, items }: { g: Gym; items?: Gym["recent"] }) {
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

export function SessionSheet({ id, unit, onClose }: { id: string; unit: string; onClose: () => void }) {
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
