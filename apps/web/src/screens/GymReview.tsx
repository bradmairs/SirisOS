import { useState } from "react";
import { Battery, Link2, Wrench } from "lucide-react";
import { gym, loadActive, newId, saveActive, shortcuts, type Exercise, type ExerciseFix, type HistoryLink, type Recovery, type Session, type SetLog } from "../api/gym";
import { useResource } from "../api/resource";
import { DecimalInput } from "../components/DecimalInput";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";

/** SirisGym 8.7, from the review: link the routine to your history, tidy imported exercises, fix a set, how it felt,
 * recovery, and doing a workout again. */

const MUSCLES = ["chest", "back", "shoulders", "biceps", "triceps", "forearms", "abs", "quads", "hamstrings", "glutes", "calves", "full body", "cardio"];
const EQUIPMENT = ["barbell", "dumbbell", "machine", "cable", "bodyweight", "kettlebell", "band", "smith", "ez bar", "trap bar", "other"];
const KIND_LABEL: Record<Exercise["kind"], string> = { weight: "weight × reps", bodyweight: "bodyweight reps", time: "timed", cardio: "cardio" };

/** The routine's exercises with little history of their own, each paired with the one your history is under. */
export function LinkHistoryCard({ onChange }: { onChange: () => void }) {
  const res = useResource("gym:links", () => gym.links(), { staleMs: 60_000 });
  const [picked, setPicked] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const links = res.data?.links ?? [];
  if (!links.length && !note) return null;
  const shown = all ? links : links.slice(0, 3);  // a few at a time, so today's workout isn't pushed off the screen
  async function decide(l: HistoryLink, into: string | null) {
    setBusy(l.exercise);
    try {
      await gym.link(l.exercise, into);
      const chosen = l.options.find((o) => o.id === into);
      setNote(chosen ? `${l.name} now uses your ${chosen.name} history (${chosen.sessions} workouts).` : `${l.name} stays as it is.`);
      await res.reload(true);
      onChange();
    } finally { setBusy(null); }
  }
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Link your history">
      <header className="widget__head"><Link2 aria-hidden="true" /><span>{links.length ? `Link your history (${links.length})` : "Link your history"}</span></header>
      {links.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Your routine uses these, but your history is under other names. Pick the one that's the same and last time, what to lift and your records come from it.</p>}
      <ul className="items">
        {shown.map((l) => {
          const choice = picked[l.exercise] ?? l.options[0]?.id;
          return (
            <li key={l.exercise} className="item gym-link">
              <span className="item__text">
                <span className="item__title">{l.name}</span>
                <span className="item__subtitle">{l.sessions ? `${l.sessions} workout${l.sessions === 1 ? "" : "s"} so far` : "Not done yet"}</span>
                <select className="field" aria-label={`Your history for ${l.name}`} value={choice} onChange={(e) => setPicked({ ...picked, [l.exercise]: e.target.value })}>
                  {l.options.map((o) => <option key={o.id} value={o.id}>{o.name} ({o.sessions})</option>)}
                </select>
              </span>
              <span className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                <button type="button" className="button button--small button--primary" disabled={busy === l.exercise} onClick={() => decide(l, choice)}>Use it</button>
                <button type="button" className="chip chip--button" disabled={busy === l.exercise} onClick={() => decide(l, null)}>Keep as is</button>
              </span>
            </li>
          );
        })}
      </ul>
      {links.length > 3 && <button type="button" className="show-more" onClick={() => setAll(!all)}>{all ? "Show fewer" : `Show all ${links.length}`}</button>}
      {note && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{note}</p>}
    </Glass>
  );
}

const ago = (hours: number | null) => (hours == null ? "not lately" : hours < 36 ? `${hours} h ago` : hours < 24 * 14 ? `${Math.round(hours / 24)} days ago` : "over 2 weeks ago");

/** How recovered each muscle is, by when it was last trained (8.7). */
export function RecoveryCard({ recovery }: { recovery: Recovery[] }) {
  if (!recovery.some((r) => r.hours != null)) return null;
  const sorted = [...recovery].sort((a, b) => (a.ready ?? 101) - (b.ready ?? 101));
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Recovery">
      <header className="widget__head"><Battery aria-hidden="true" /><span>Recovery</span></header>
      <ul className="gym-recovery" aria-label="How recovered each muscle is">
        {sorted.map((r) => (
          <li key={r.muscle} className={`gym-recovery__item gym-recovery--${r.ready == null ? "rested" : r.ready >= 100 ? "ready" : r.ready >= 60 ? "nearly" : "tired"}`}
            title={`${r.muscle}: trained ${ago(r.hours)}${r.via === "helper" ? ", helping another lift" : ""}`}>
            <span className="gym-recovery__name">{r.muscle}</span>
            <span className="gym-recovery__state">{r.ready == null ? "fresh" : r.ready >= 100 ? "ready" : `${r.ready}%`}</span>
            <span className="gym-recovery__when muted">{ago(r.hours)}{r.via === "helper" ? " · helping" : ""}</span>
          </li>
        ))}
      </ul>
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>By the usual rule of thumb: about a day or so for arms, calves and abs, two for the upper body, three for legs; half that for a muscle that only helped (the triceps in a bench press).</p>
    </Glass>
  );
}

const describe = (c: ExerciseFix["change"]) => [c.kind && KIND_LABEL[c.kind], c.equipment, c.primary && `works ${c.primary}`].filter(Boolean).join(", ");

/** Imported exercises whose kind, equipment or main muscle is wrong (8.7): apply the suggestion, or keep as is. */
export function ExerciseFixesCard({ onChange }: { onChange: () => void }) {
  const res = useResource("gym:fixes", () => gym.exerciseFixes(), { staleMs: 60_000 });
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const fixes = res.data?.fixes ?? [];
  if (!fixes.length && !note) return null;
  async function run(ids: string[], keep: boolean) {
    setBusy(true);
    try {
      const r = await gym.applyFixes(ids, keep);
      setNote(keep ? "Kept as they are." : `Tidied ${r.changed} exercise${r.changed === 1 ? "" : "s"}. A copy of your gym file was saved first.`);
      await res.reload(true);
      onChange();
    } finally { setBusy(false); }
  }
  const shown = all ? fixes : fixes.slice(0, 6);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Tidy imported exercises">
      <header className="widget__head"><Wrench aria-hidden="true" /><span>{fixes.length ? `Tidy imported exercises (${fixes.length})` : "Tidy imported exercises"}</span>
        {fixes.length > 1 && <button type="button" className="button button--small" style={{ marginLeft: "auto" }} disabled={busy} onClick={() => run(fixes.map((f) => f.id), false)}>Fix all</button>}
      </header>
      {fixes.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>From the JEFIT import: these say the wrong kind, equipment or muscle, which skews sets per muscle, warm-ups and plates.</p>}
      <ul className="items">
        {shown.map((f) => (
          <li key={f.id} className="item gym-fix-row">
            <span className="item__text">
              <span className="item__title">{f.name}</span>
              <span className="item__subtitle">{describe(f.change)} <span className="muted">(now {describe(Object.fromEntries(Object.keys(f.change).map((k) => [k, f.now[k as keyof ExerciseFix["now"]]])))})</span></span>
            </span>
            <span className="row" style={{ gap: 6 }}>
              <button type="button" className="chip chip--button" disabled={busy} onClick={() => run([f.id], false)}>Fix</button>
              <button type="button" className="chip chip--button" disabled={busy} onClick={() => run([f.id], true)}>Keep</button>
            </span>
          </li>
        ))}
      </ul>
      {fixes.length > 6 && <button type="button" className="show-more" onClick={() => setAll(!all)}>{all ? "Show fewer" : `Show all ${fixes.length}`}</button>}
      {note && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{note}</p>}
    </Glass>
  );
}

/** Change one of your own exercises (8.7): its name, main muscle, equipment and how it's logged. */
/** The muscles that help (9.44): tap to add or take one away. The main muscle isn't offered. */
export function HelperMuscles({ primary, value, onChange }: { primary: string; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <div className="stack" style={{ gap: 4 }}>
      <span className="muted">Helped by</span>
      <div className="row" style={{ gap: 6, flexWrap: "wrap" }} role="group" aria-label="Helper muscles">
        {MUSCLES.filter((m) => m !== primary && m !== "cardio").map((m) => {
          const on = value.includes(m);
          return <button key={m} type="button" aria-pressed={on} className={`chip chip--button ${on ? "chip--active" : ""}`}
            onClick={() => onChange(on ? value.filter((x) => x !== m) : [...value, m].slice(0, 6))}>{m}</button>;
        })}
      </div>
      <span className="muted" style={{ fontSize: 12 }}>Each set counts half a set for each, in sets per muscle and recovery.</span>
    </div>
  );
}

export function EditExerciseSheet({ exercise, onClose, onSaved }: { exercise: Exercise; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ name: exercise.name, primary: exercise.primary, secondary: exercise.secondary ?? [], equipment: exercise.equipment, kind: exercise.kind });
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    try { await gym.changeExercise(exercise.id, f); onSaved(); }
    catch (e) { setProblem(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return (
    <Sheet label="Edit exercise" onClose={onClose}>
      <div className="stack" style={{ gap: 10 }}>
        <h2 className="sheet__title">Edit {exercise.name}</h2>
        <input className="field" aria-label="Name" value={f.name} maxLength={80} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <label className="stack" style={{ gap: 4 }}><span className="muted">Main muscle</span>
          <select className="field" aria-label="Main muscle" value={f.primary} onChange={(e) => setF({ ...f, primary: e.target.value, secondary: f.secondary.filter((m) => m !== e.target.value) })}>{MUSCLES.map((m) => <option key={m}>{m}</option>)}</select></label>
        <HelperMuscles primary={f.primary} value={f.secondary} onChange={(secondary) => setF({ ...f, secondary })} />
        <label className="stack" style={{ gap: 4 }}><span className="muted">Equipment</span>
          <select className="field" aria-label="Equipment" value={f.equipment} onChange={(e) => setF({ ...f, equipment: e.target.value })}>{EQUIPMENT.map((m) => <option key={m}>{m}</option>)}</select></label>
        <label className="stack" style={{ gap: 4 }}><span className="muted">Logged as</span>
          <select className="field" aria-label="Logged as" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value as Exercise["kind"] })}>
            {(Object.keys(KIND_LABEL) as Exercise["kind"][]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}</select></label>
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>Its sets stay as they are.</p>
        {problem && <p className="tone-critical" role="alert" style={{ margin: 0 }}>{problem}</p>}
        <button type="button" className="button button--primary" style={{ alignSelf: "flex-start" }} disabled={busy || !f.name.trim()} onClick={save}>Save</button>
      </div>
    </Sheet>
  );
}

/** Correct one workout's sets of an exercise (8.7), e.g. a 210 kg squat that was 21 or 70. */
export function FixSetsForm({ session, exercise, sets, onDone, onCancel }: {
  session: string; exercise: string; sets: SetLog[]; onDone: () => void; onCancel: () => void;
}) {
  const [rows, setRows] = useState(sets.map((x) => ({ weight: x.weight ?? null, reps: x.reps ?? null, seconds: x.seconds ?? null, km: x.km ?? null })));
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    try { await gym.fixSets(session, exercise, rows); onDone(); }
    catch (e) { setProblem(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return (
    <div className="stack gym-fix" style={{ gap: 6 }} aria-label="Fix these sets">
      {rows.map((r, i) => (
        <div key={i} className="row" style={{ gap: 6, alignItems: "center" }}>
          <span className="muted" style={{ width: 22 }}>{i + 1}</span>
          <DecimalInput className="field gym-sets__in" aria-label={`Set ${i + 1} weight`} value={r.weight} onValue={(v) => setRows(rows.map((x, j) => (j === i ? { ...x, weight: v } : x)))} />
          <span className="muted">×</span>
          <input className="field gym-sets__in" inputMode="numeric" aria-label={`Set ${i + 1} reps`} value={r.reps ?? ""}
            onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, reps: e.target.value === "" ? null : Number(e.target.value) } : x)))} />
        </div>
      ))}
      {problem && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 13 }}>{problem}</p>}
      <div className="row" style={{ gap: 8 }}>
        <button type="button" className="button button--small button--primary" disabled={busy} onClick={save}>Save</button>
        <button type="button" className="chip chip--button" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

const FEELS = [[1, "😣", "Awful"], [2, "😕", "Hard going"], [3, "😐", "OK"], [4, "🙂", "Good"], [5, "😄", "Great"]] as const;

/** How it felt (8.7): one tap after finishing, kept with the workout. */
export function FeelPicker({ session, start = null }: { session: string; start?: number | null }) {
  const [feel, setFeel] = useState<number | null>(start);
  const [failed, setFailed] = useState(false);
  return (
    <div className="stack" style={{ gap: 6 }}>
      <span className="muted" style={{ fontSize: 13 }}>How did it feel?</span>
      <div className="row gym-feel" role="radiogroup" aria-label="How it felt">
        {FEELS.map(([n, face, label]) => (
          <button key={n} type="button" role="radio" aria-checked={feel === n} aria-label={label} title={label} className={`chip chip--button ${feel === n ? "chip--active" : ""}`}
            onClick={() => { setFeel(n); gym.feel(session, n).then(() => setFailed(false)).catch(() => setFailed(true)); }}>{face}</button>
        ))}
      </div>
      {failed && <span className="tone-warning" style={{ fontSize: 12 }}>Couldn't save that: SirisOS isn't answering.</span>}
    </div>
  );
}

/** Do a saved workout again (8.7): the same exercises and sets, with its weights and reps filled in, none ticked. */
export async function repeatWorkout(navigate: (to: string) => void, id: string, shortcut?: string): Promise<string | null> {
  if (loadActive()) return "Finish or discard the workout in progress first.";
  const s = await gym.session(id);
  const fresh: Session = {
    id: newId(), title: s.title, started_at: new Date().toISOString(), routine_id: s.routine_id ?? null, day: s.day ?? null, gym: s.gym ?? null,
    entries: s.entries.map(({ exercise, sets, group }) => ({ exercise, group: group ?? null,
      sets: sets.filter((x) => x.done).map((x) => ({ weight: x.weight ?? null, reps: x.reps ?? null, seconds: x.seconds ?? null, km: x.km ?? null, type: x.type, done: false })) })),
  };
  saveActive(fresh);
  navigate("/gym/workout");
  shortcuts.run(shortcut, "/gym/workout");
  return null;
}
