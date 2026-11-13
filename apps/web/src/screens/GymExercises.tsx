import { useState } from "react";
import { Dumbbell, HeartPulse, ListPlus, Pencil, Plus, Search } from "lucide-react";
import { useResource } from "../api/resource";
import { gym, type Exercise, type Duplicate, type MergeDone, type ExerciseDetail, type Gym } from "../api/gym";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";
import { FitnessLine, VideosCard } from "./GymCards";
import { EditExerciseSheet, ExerciseFixesCard, FixSetsForm, HelperMuscles } from "./GymReview";
import { EQUIPMENT, MUSCLES, fmtDay, kg } from "./GymShared";

/** SirisGym's Exercises tab and an exercise's sheet (split out of Gym.tsx in 8.9). */

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

export function ExercisesView({ g, onChange }: { g: Gym; onChange: () => void }) {
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
export function DuplicatesCard({ onChange }: { onChange: () => void }) {
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

export function NewExercise({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ name: "", primary: "chest", secondary: [] as string[], equipment: "barbell", kind: "weight" as Exercise["kind"] });
  return (
    <Sheet label="Your own exercise" onClose={onClose}>
      <div className="stack" style={{ gap: 8 }}>
        <h2 className="sheet__title">Your own exercise</h2>
        <input className="field" placeholder="Name" aria-label="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })}
          onBlur={async () => {
            // 9.44: the muscles the name says, unless you've already chosen helpers.
            if (!f.name.trim() || f.secondary.length) return;
            try { const a = await gym.anatomy(f.name.trim()); if (a.primary) setF((x) => ({ ...x, primary: a.primary!, secondary: a.secondary })); } catch { /* choose them yourself */ }
          }} />
        <select className="field" aria-label="Main muscle" value={f.primary} onChange={(e) => setF({ ...f, primary: e.target.value, secondary: f.secondary.filter((m) => m !== e.target.value) })}>{MUSCLES.map((m) => <option key={m}>{m}</option>)}</select>
        <HelperMuscles primary={f.primary} value={f.secondary} onChange={(secondary) => setF({ ...f, secondary })} />
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

export function E1rmChart({ series }: { series: ExerciseDetail["series"] }) {
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

/** Form cues for an exercise (8.8): a built-in few for the big lifts, or your own. */
export function CuesEditor({ id, cues, yours, onSaved }: { id: string; cues: string; yours: boolean; onSaved: () => void }) {
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

/** The Watch's heart rate lined up with each set (6.96): the effort per exercise, worked out by SirisAI. */
export function EffortCard({ id }: { id: string }) {
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
