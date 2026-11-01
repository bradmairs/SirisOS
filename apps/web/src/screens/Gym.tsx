import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { CalendarDays, ChevronRight, Dumbbell, Flame, ListPlus, Medal, Play, Plus, Search, Settings2, Trash2, Trophy, Upload } from "lucide-react";
import { useResource } from "../api/resource";
import { gym, loadActive, newId, saveActive, type Exercise, type ExerciseDetail, type Gym, type GymProfile, type GymSettings, type ImportPreview, type ImportUnit, type Progression, type Routine, type Session } from "../api/gym";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";
import { Sheet } from "../components/Sheet";

/** SirisGYM (6.5; renamed and given its importer in 6.6): start today's workout, routines, history and the exercises with your records. */
const VIEWS = [{ id: "today", label: "Today" }, { id: "routines", label: "Routines" }, { id: "history", label: "History" }, { id: "exercises", label: "Exercises" },
  { id: "settings", label: "Settings" }] as const;
type View = (typeof VIEWS)[number]["id"];
const MUSCLES = ["chest", "back", "shoulders", "biceps", "triceps", "forearms", "abs", "quads", "hamstrings", "glutes", "calves", "full body", "cardio"];
const EQUIPMENT = ["barbell", "dumbbell", "machine", "cable", "bodyweight", "kettlebell", "band", "smith", "ez bar", "trap bar", "other"];
export const fmtDay = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
export const kg = (v: number | null | undefined, unit = "kg") => (v == null ? "–" : `${Number.isInteger(v) ? v : v.toFixed(1)} ${unit}`);

export function useGym() {
  return useResource<Gym>("gym", () => gym.get(), { staleMs: 30_000, persist: true });
}

/** Start a workout: from a routine day (with last time, what to lift and warm-ups), or empty. */
export async function startWorkout(navigate: (to: string) => void, routine?: Routine, day?: number, gymId?: string) {
  const now = new Date().toISOString();
  let s: Session = { id: newId(), title: "Workout", started_at: now, entries: [], gym: gymId ?? null };
  if (routine) {
    const p = await gym.plan(routine.id, day, gymId);
    s = { ...s, title: p.title, routine_id: routine.id, day: p.day, entries: p.exercises.map((e) => ({
      exercise: e.exercise,
      group: e.group ?? null,
      sets: [
        ...(e.warmups ?? []).map((w) => ({ weight: w.weight, reps: w.reps, done: false, type: "warmup" as const })),
        ...Array.from({ length: e.sets }, (_, i) => ({ weight: e.suggest.per_set?.[i] ?? e.suggest.weight ?? e.last[i]?.weight ?? null, reps: null, done: false, type: "normal" as const })),
      ],
    })) };
    try { window.sessionStorage.setItem(`sirisos.gym.plan.${s.id}`, JSON.stringify(p)); } catch { /* fine */ }
  }
  saveActive(s);
  navigate("/gym/workout");
}

export function GymScreen() {
  const res = useGym();
  const [params, setParams] = useSearchParams();
  const view = (VIEWS.find((v) => v.id === params.get("view"))?.id ?? "today") as View;
  useEffect(() => { document.title = "SirisGYM · SirisOS"; }, []);
  const g = res.data;
  return (
    <>
      <PageHead eyebrow={g ? `${g.total_sessions} workouts · ${g.streak_weeks}-week streak` : "Gym"} title="SirisGYM" />
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
          {view === "today" && <TodayView g={g} />}
          {view === "routines" && <RoutinesView g={g} onChange={() => res.reload?.(true)} />}
          {view === "history" && <HistoryView g={g} onChange={() => res.reload?.(true)} />}
          {view === "exercises" && <ExercisesView g={g} onChange={() => res.reload?.(true)} />}
          {view === "settings" && <SettingsView g={g} onChange={() => res.reload?.(true)} />}
        </div>
      )}
    </>
  );
}

function TodayView({ g }: { g: Gym }) {
  const navigate = useNavigate();
  const active = loadActive();
  const routine = g.routines.find((r) => r.id === g.active?.routine);
  const next = routine?.days[g.active?.next_day ?? 0];
  const [busy, setBusy] = useState(false);
  const [gymId, setGymId] = useState(g.settings.current_gym);
  const go = async (r?: Routine, d?: number) => { setBusy(true); try { await startWorkout(navigate, r, d, gymId); } finally { setBusy(false); } };
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
        {routine && next ? (
          <>
            <p style={{ margin: 0, fontSize: 16 }}><strong>{routine.name}: {next.name}</strong></p>
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>{next.exercises.map((e) => g.exercises.find((x) => x.id === e.exercise)?.name ?? e.exercise).join(" · ")}</p>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button type="button" className="button button--primary" disabled={busy || !!active} onClick={() => go(routine)}>Start {next.name}</button>
              {routine.days.length > 1 && routine.days.map((d, i) => i !== g.active?.next_day && (
                <button key={d.name} type="button" className="chip chip--button" disabled={busy || !!active} onClick={() => go(routine, i)}>{d.name}</button>
              ))}
            </div>
          </>
        ) : (
          <p className="muted" style={{ margin: 0 }}>No routine yet: pick a starter one under Routines, or just start an empty workout.</p>
        )}
        <button type="button" className="button" style={{ alignSelf: "flex-start" }} disabled={busy || !!active} onClick={() => go()}>Empty workout</button>
      </Glass>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="This week">
        <header className="widget__head"><Flame aria-hidden="true" /><span>This week</span></header>
        <div className="metrics">
          <div><div className="metric__value">{g.week.sessions}</div><div className="metric__label">Workouts</div></div>
          <div><div className="metric__value">{Math.round(g.week.volume).toLocaleString()}</div><div className="metric__label">Volume ({g.settings.unit})</div></div>
          <div><div className="metric__value">{g.streak_weeks}</div><div className="metric__label">Weeks in a row</div></div>
        </div>
        {muscles.length > 0 && (
          <ul className="gym-muscles" aria-label="Sets by muscle this week">
            {muscles.map(([m, n]) => (
              <li key={m}><span className="gym-muscles__name">{m}</span><span className="gym-muscles__bar"><span style={{ width: `${(n / most) * 100}%` }} /></span><span className="muted">{n}</span></li>
            ))}
          </ul>
        )}
      </Glass>
      {g.recent.length > 0 && <RecentList g={g} />}
    </>
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
              <span className="item__subtitle">{fmtDay(s.date)}{s.minutes ? ` · ${s.minutes} min` : ""} · {s.sets} sets · {Math.round(s.volume).toLocaleString()} {g.settings.unit}</span>
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
  return (
    <Sheet label="Workout" onClose={onClose}>
      {!s ? <div className="skeleton" style={{ height: 160 }} /> : (
        <div className="stack" style={{ gap: 10 }}>
          <h2 className="sheet__title">{s.title}</h2>
          <p className="muted" style={{ margin: 0 }}>{fmtDay(s.started_at)}{s.summary.minutes ? ` · ${s.summary.minutes} min` : ""} · {Math.round(s.summary.volume).toLocaleString()} {unit} lifted</p>
          {s.records.length > 0 && <ul className="items">{s.records.map((r) => <li key={r.text} className="item"><Trophy size={16} className="tone-warning" aria-hidden="true" /><span className="item__text"><span className="item__title">{r.text}</span></span></li>)}</ul>}
          {s.entries.map((e) => (
            <div key={e.exercise}>
              <strong>{e.name}</strong>
              <p className="muted" style={{ margin: 0, fontSize: 14 }}>{e.sets.filter((x) => x.done).map((x) => x.weight ? `${x.weight}×${x.reps ?? "–"}` : x.seconds ? `${x.seconds}s` : `${x.reps ?? "–"} reps`).join(", ")}</p>
            </div>
          ))}
          <button type="button" className="icon-link" style={{ alignSelf: "flex-start" }} onClick={async () => { if (window.confirm("Delete this workout?")) { await gym.deleteSession(id); onClose(); window.location.reload(); } }}>
            <Trash2 size={14} aria-hidden="true" /> Delete
          </button>
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
      <header className="widget__head"><Flame aria-hidden="true" /><span>The last year</span><span className="widget__source">{weeks} workouts</span></header>
      <div className="gym-heat" role="img" aria-label={`${weeks} workouts in the last year`}>
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
      setDone(`Imported ${r.workouts.toLocaleString()} workouts and ${r.sets.toLocaleString()} sets${r.new_exercises ? `, with ${r.new_exercises} new exercises of yours` : ""}.`);
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
            {pre.replacing > 0 ? ` ${pre.replacing} of those days were imported before and will be replaced.` : ""}</p>
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
            {d.exercises.map((e, k) => (
              <div key={`${e.exercise}-${k}`} className="row gym-plan-row">
                <span className="gym-plan-row__name">{g.exercises.find((x) => x.id === e.exercise)?.name ?? e.exercise}</span>
                <input className="field" type="number" min={1} max={20} aria-label="Sets" value={e.sets} onChange={(ev) => setDay(i, { ...d, exercises: d.exercises.map((x, j) => (j === k ? { ...x, sets: Number(ev.target.value) || 1 } : x)) })} />
                <span className="muted">×</span>
                <input className="field" aria-label="Reps" value={e.reps} onChange={(ev) => setDay(i, { ...d, exercises: d.exercises.map((x, j) => (j === k ? { ...x, reps: ev.target.value } : x)) })} />
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
      {open && <ExerciseSheet id={open} unit={g.settings.unit} onClose={() => setOpen(null)} />}
      {adding && <NewExercise onClose={() => setAdding(false)} onSaved={() => { setAdding(false); onChange(); }} />}
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
export function ExerciseSheet({ id, unit, onClose }: { id: string; unit: string; onClose: () => void }) {
  const res = useResource<ExerciseDetail>(`gym:exercise:${id}`, () => gym.exercise(id), {});
  const d = res.data;
  return (
    <Sheet label="Exercise" onClose={onClose}>
      {!d ? <div className="skeleton" style={{ height: 160 }} /> : (
        <div className="stack" style={{ gap: 10 }}>
          <h2 className="sheet__title">{d.exercise.name}</h2>
          <p className="muted" style={{ margin: 0 }}>{d.exercise.primary}{d.exercise.secondary.length ? `, with ${d.exercise.secondary.join(", ")}` : ""} · {d.exercise.equipment}</p>
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
              <ul className="items" aria-label="History">
                {d.history.map((h) => (
                  <li key={h.session} className="item"><span className="item__text"><span className="item__title">{fmtDay(h.date)}</span>
                    <span className="item__subtitle">{h.sets.map((x) => (x.weight ? `${x.weight}×${x.reps ?? "–"}` : x.seconds ? `${x.seconds}s` : `${x.reps ?? "–"}`)).join(", ")}{h.e1rm ? ` · est. 1RM ${h.e1rm}` : ""}</span></span></li>
                ))}
              </ul>
            </>
          )}
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

/** SirisGYM's settings (6.7): rest, the weight step, warm-ups, and each gym with its bar, plates, dumbbells and machines. */
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
        <label className="gym-setting">Weight step (kg)<input className="field" type="number" step={0.25} min={0.25} max={20} value={s.increment} onChange={(e) => setS({ ...s, increment: Number(e.target.value) || 2.5 })} /></label>
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
      <div className="row" style={{ gap: 8 }}>
        <button type="button" className="button" onClick={() => setS({ ...s, gyms: [...s.gyms, { id: newId(), name: `Gym ${s.gyms.length + 1}`, bar: 20, plates: [25, 20, 15, 10, 5, 2.5, 1.25], dumbbells: [], stack_step: null }] })}>
          <Plus size={14} aria-hidden="true" /> Add a gym</button>
        <button type="button" className="button button--primary" onClick={save}>Save settings</button>
        {saved && <span role="status" className="muted">Saved.</span>}
      </div>
    </>
  );
}
