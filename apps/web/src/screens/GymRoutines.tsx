import { useState } from "react";
import { ArrowDown, ArrowUp, ListPlus, Medal, Plus, Sparkles, Trash2 } from "lucide-react";
import { useResource } from "../api/resource";
import { gym, moveEntry, type BuildEquipment, type BuildGoal, type Built, type Gym, type Progression, type Routine } from "../api/gym";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";
import { ExercisePicker } from "./GymExercises";

/** SirisGym's Routines tab: the builder and the editor (split out of Gym.tsx in 8.9). */

export function RoutinesView({ g, onChange }: { g: Gym; onChange: () => void }) {
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

export const AREAS = ["shoulder", "elbow", "wrist", "lower back", "knee"];

/** Build me a programme (6.9): a goal in words or picked, drafted into the routine editor to change and save. */
export function BuilderCard({ onDraft }: { onDraft: (r: Routine) => void }) {
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

export function RoutineEditor({ g, start, onClose, onSaved }: { g: Gym; start: Routine; onClose: () => void; onSaved: () => void }) {
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
