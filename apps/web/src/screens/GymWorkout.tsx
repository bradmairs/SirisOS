import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeftRight, Check, Link2, Mic, Plus, Timer, Trash2, Trophy, X } from "lucide-react";
import { e1rm, gym, loadActive, parseSpoken, plates, saveActive, shortcuts, type Exercise, type GymRecord, type Plan, type Session, type SetLog, type Summary } from "../api/gym";
import { keep, unreachable } from "../api/outbox";
import { brain } from "../api/hub";
import { micUnavailableReason, startRecording } from "../api/voice";
import { Glass } from "../components/Glass";
import { ExercisePicker, ExerciseSheet, kg, useGym } from "./Gym";
import { Sheet } from "../components/Sheet";
import { useResource } from "../api/resource";
import { FilmButton } from "./GymCards";

/** The workout in progress (6.5): log each set against last time, a rest timer after each one,
 * plates for the bar, and finish (it waits on the phone if there's no signal). */
export function GymWorkoutScreen() {
  const navigate = useNavigate();
  const g = useGym().data;
  const [s, setS] = useState<Session | null>(() => loadActive());
  const [picking, setPicking] = useState(false);
  const [openEx, setOpenEx] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [rest, setRest] = useState<{ until: number; total: number } | null>(null);
  const [done, setDone] = useState<{ summary?: Summary; records?: GymRecord[]; offline?: boolean } | null>(null);
  const [, tick] = useState(0);
  const [listening, setListening] = useState(false);
  const [swapping, setSwapping] = useState<number | null>(null);
  const plan = useMemo<Plan | null>(() => { try { return s ? JSON.parse(window.sessionStorage.getItem(`sirisos.gym.plan.${s.id}`) ?? "null") : null; } catch { return null; } }, [s?.id]);
  useEffect(() => { const t = window.setInterval(() => tick((n) => n + 1), 1000); return () => window.clearInterval(t); }, []);
  useEffect(() => { document.title = "Workout · SirisOS"; }, []);
  useEffect(() => {
    if (rest && Date.now() >= rest.until) {
      setRest(null);
      try { navigator.vibrate?.([200, 100, 200]); } catch { /* not on this device */ }
    }
  });
  if (done) return <Finished done={done} unit={g?.settings.unit ?? "kg"} />;
  if (!s) {
    return (
      <Glass className="widget" style={{ marginTop: 16, minHeight: 0 }}>
        <p style={{ margin: 0 }}>No workout in progress.</p>
        <Link to="/gym" className="button button--primary" style={{ alignSelf: "flex-start" }}>Start one</Link>
      </Glass>
    );
  }
  const unit = g?.settings.unit ?? "kg";
  const byId = new Map((g?.exercises ?? []).map((e) => [e.id, e] as const));
  const update = (next: Session) => { setS(next); saveActive(next); };
  const setSet = (ei: number, si: number, patch: Partial<SetLog>) =>
    update({ ...s, entries: s.entries.map((e, i) => (i === ei ? { ...e, sets: e.sets.map((x, j) => (j === si ? { ...x, ...patch } : x)) } : e)) });
  const restFor = (exercise: string) => plan?.exercises.find((p) => p.exercise === exercise)?.rest_s ?? g?.settings.rest_s ?? 90;
  const here = g?.settings.gyms?.find((x) => x.id === s.gym) ?? (g ? { bar: g.settings.bar, plates: g.settings.plates } : undefined);
  /** In a superset, rest comes after the last exercise of the group (6.7). */
  const lastInGroup = (ei: number) => { const grp = s.entries[ei].group; return !grp || s.entries.map((e) => e.group).lastIndexOf(grp) === ei; };
  const link = (ei: number) => {
    const used = new Set(s.entries.map((e) => e.group).filter(Boolean));
    const letter = s.entries[ei].group ?? s.entries[ei + 1]?.group ?? ["A", "B", "C", "D", "E", "F"].find((l) => !used.has(l)) ?? "A";
    update({ ...s, entries: s.entries.map((e, i) => (i === ei || i === ei + 1 ? { ...e, group: letter } : e)) });
  };
  /** What comes after this set, for the rest-over notification. */
  const nextText = (ei: number, si: number) => {
    for (let i = ei; i < s.entries.length; i++) {
      const sets = s.entries[i].sets;
      const j = sets.findIndex((x, k) => !x.done && (i > ei || k > si));
      if (j >= 0) { const x = sets[j]; return `${byId.get(s.entries[i].exercise)?.name ?? s.entries[i].exercise}, set ${j + 1}${x.weight ? `: ${x.weight} kg` : ""}`; }
    }
    return "That was the last set: finish when you're ready.";
  };
  /** Rest, with a push to the lock screen when it's over (6.9). */
  const startRest = (t: number, next: string) => {
    setRest(t ? { until: Date.now() + t * 1000, total: t } : null);
    if (t) gym.rest(t, next).catch(() => {});
  };
  const stopRest = () => { setRest(null); gym.stopRest().catch(() => {}); };
  /** Log the next set by voice (6.9): "100 by 5", "bench 82.5 for 8 RPE 8". */
  async function voice() {
    if (!s) return;
    const why = micUnavailableReason();
    if (why) { setInfo(why); return; }
    setListening(true);
    try {
      const rec = await startRecording({ stopOnSilence: true, maxSeconds: 8, sampleRate: 16000 });
      const { text } = await brain.transcribe(await rec.done);
      const said = parseSpoken(text ?? "");
      if (!said) { setInfo(`Didn't catch a set in "${text}". Try "100 by 5".`); return; }
      const words = (said.name ?? "").split(" ").filter((w) => w.length > 2);
      const named = words.length ? s.entries.findIndex((e) => words.some((w) => (byId.get(e.exercise)?.name ?? e.exercise).toLowerCase().includes(w))) : -1;
      const ei = named >= 0 ? named : s.entries.findIndex((e) => e.sets.some((x) => !x.done));
      if (ei < 0) { setInfo("Every set's done: add one first."); return; }
      const entry = s.entries[ei];
      let si = entry.sets.findIndex((x) => !x.done && x.type !== "warmup");
      if (si < 0) si = entry.sets.findIndex((x) => !x.done);
      const patch = { reps: said.reps, done: true, at: new Date().toISOString(), ...(said.weight !== undefined ? { weight: said.weight } : {}), ...(said.rpe ? { rpe: said.rpe } : {}) };
      const sets = si >= 0 ? entry.sets.map((x, j) => (j === si ? { ...x, ...patch } : x)) : [...entry.sets, { type: "normal" as const, weight: said.weight ?? entry.sets.at(-1)?.weight ?? null, ...patch }];
      update({ ...s, entries: s.entries.map((e, i) => (i === ei ? { ...e, sets } : e)) });
      const name = byId.get(entry.exercise)?.name ?? entry.exercise;
      setInfo(`Logged ${name}: ${said.weight != null ? `${said.weight} × ` : ""}${said.reps}${said.rpe ? ` at RPE ${said.rpe}` : ""}.`);
      if (lastInGroup(ei)) startRest(restFor(entry.exercise), nextText(ei, si < 0 ? entry.sets.length : si));
    } catch (e) {
      setInfo(e instanceof Error ? e.message : "Couldn't listen.");
    } finally { setListening(false); }
  }
  const unlink = (ei: number) => update({ ...s, entries: s.entries.map((e, i) => (i === ei ? { ...e, group: null } : e)) });
  const elapsed = Math.floor((Date.now() - new Date(s.started_at).getTime()) / 1000);
  const doneSets = s.entries.reduce((n, e) => n + e.sets.filter((x) => x.done).length, 0);

  /** Discarding stops the Watch too (7.61): the finish Shortcut runs, told "discarded", then comes back to SirisGym. */
  function discard() {
    if (!window.confirm("Discard this workout?")) return;
    gym.stopRest().catch(() => {});
    saveActive(null);
    if (!shortcuts.run(g?.settings.shortcut_finish, "/gym", "discarded")) navigate("/gym");
  }

  async function finish() {
    if (!s) return;
    const final: Session = { ...s, ended_at: new Date().toISOString(), entries: s.entries.map((e) => ({ ...e, sets: e.sets.filter((x) => x.done) })).filter((e) => e.sets.length) };
    if (!final.entries.length) { setInfo("Tick at least one set first, or discard it."); return; }
    const undone = s.entries.reduce((n, e) => n + e.sets.filter((x) => !x.done).length, 0);
    if (undone && !window.confirm(`${undone} set${undone === 1 ? " isn't" : "s aren't"} ticked, and won't be saved. Finish anyway?`)) return;
    gym.stopRest().catch(() => {});
    try {
      const r = await gym.finish(final);
      saveActive(null);
      setDone(r);
      shortcuts.run(g?.settings.shortcut_finish, "/gym", "finished");
    } catch (e) {
      if (unreachable(e) && keep({ kind: "gym", session: final })) {
        saveActive(null);
        setDone({ offline: true });
        shortcuts.run(g?.settings.shortcut_finish, "/gym", "finished");
      } else {
        setInfo(e instanceof Error ? e.message : "Couldn't save it.");
      }
    }
  }

  return (
    <>
      <div className="gym-top">
        <div>
          <h1 className="gym-top__title">{s.title}</h1>
          <span className="muted">{Math.floor(elapsed / 3600) ? `${Math.floor(elapsed / 3600)}:` : ""}{String(Math.floor(elapsed / 60) % 60).padStart(2, "0")}:{String(elapsed % 60).padStart(2, "0")} · {doneSets} sets</span>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <button type="button" className="button" aria-label="Log a set by voice" aria-pressed={listening} disabled={listening} onClick={voice}><Mic size={16} aria-hidden="true" />{listening ? " Listening…" : ""}</button>
          <button type="button" className="button button--primary" onClick={finish}>Finish</button>
        </div>
      </div>
      {info && <p className="tone-warning" role="status">{info}</p>}
      <div className="stack" style={{ marginTop: 12 }}>
        {s.entries.map((entry, ei) => {
          const ex = byId.get(entry.exercise);
          const p = plan?.exercises.find((x) => x.exercise === entry.exercise);
          return (
            <Glass key={`${entry.exercise}-${ei}`} as="section" className={`widget gym-entry ${entry.group ? "gym-entry--grouped" : ""}`} style={{ minHeight: 0 }} aria-label={ex?.name ?? entry.exercise}>
              {entry.group && <span className="gym-group">SUPERSET {entry.group}<button type="button" className="icon-link" aria-label={`Take ${ex?.name} out of the superset`} onClick={() => unlink(ei)}><X size={10} aria-hidden="true" /></button></span>}
              <header className="widget__head">
                <button type="button" className="icon-link gym-entry__name" onClick={() => setOpenEx(entry.exercise)}>{ex?.name ?? entry.exercise}</button>
                <button type="button" className="icon-link" aria-label={`Swap ${ex?.name ?? entry.exercise}`} title="Swap for another exercise" onClick={() => setSwapping(ei)}><ArrowLeftRight size={14} aria-hidden="true" /></button>
                <button type="button" className="widget__source icon-link" aria-label={`Remove ${ex?.name}`} onClick={() => update({ ...s, entries: s.entries.filter((_, i) => i !== ei) })}><X size={14} aria-hidden="true" /></button>
              </header>
              {p && <p className="muted" style={{ margin: 0, fontSize: 12 }}>{p.sets} × {p.reps} · {p.suggest.why}</p>}
              {p?.suggest.last_note && <p className="muted" style={{ margin: 0, fontSize: 12 }}>Last time's note: {p.suggest.last_note}</p>}
              {p?.niggle && <p className="tone-warning" style={{ margin: 0, fontSize: 12 }}>{p.niggle.why}{p.niggle.from ? ` (instead of ${byId.get(p.niggle.from)?.name ?? p.niggle.from})` : ""}</p>}
              {p?.rest_learned && <p className="muted" style={{ margin: 0, fontSize: 12 }}>Rest {p.rest_learned.seconds} s, not {p.rest_learned.planned}: {p.rest_learned.why}</p>}
              <SetTable ex={ex} sets={entry.sets} last={(p?.last ?? []).length ? p!.last : []} unit={unit} settings={here}
                onChange={(si, patch) => {
                  setSet(ei, si, patch);
                  if (patch.done) {
                    const t = lastInGroup(ei) ? restFor(entry.exercise) : 0;
                    if (t) startRest(t, nextText(ei, si)); else setRest(null);
                  }
                }}
                onRemove={(si) => update({ ...s, entries: s.entries.map((e, i) => (i === ei ? { ...e, sets: e.sets.filter((_, j) => j !== si) } : e)) })} />
              <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }}
                onClick={() => { const prev = entry.sets.at(-1); update({ ...s, entries: s.entries.map((e, i) => (i === ei ? { ...e, sets: [...e.sets, { weight: prev?.weight ?? null, reps: null, done: false, type: "normal" }] } : e)) }); }}>
                <Plus size={12} aria-hidden="true" /> Set
              </button>
              {(() => {
                // Filmed during the set it's for: the next one to tick (or the last, once they're all done).
                const work = entry.sets.filter((x) => x.type !== "warmup");
                const i = work.findIndex((x) => !x.done);
                const at = i >= 0 ? work[i] : work.at(-1);
                return <FilmButton exercise={entry.exercise} session={s.id} set={i >= 0 ? i + 1 : work.length || undefined} weight={at?.weight ?? null}
                  reps={at?.reps ?? null} name={ex?.name ?? entry.exercise} />;
              })()}
              <input className="field" style={{ fontSize: 13 }} placeholder="Note for this exercise (a niggle, the setup, the seat height)" aria-label={`Note for ${ex?.name ?? entry.exercise}`}
                value={entry.note ?? ""} onChange={(e) => update({ ...s, entries: s.entries.map((x, i) => (i === ei ? { ...x, note: e.target.value } : x)) })} />
              {ei < s.entries.length - 1 && !(entry.group && entry.group === s.entries[ei + 1].group) && (
                <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => link(ei)}><Link2 size={12} aria-hidden="true" /> Superset with the next</button>
              )}
            </Glass>
          );
        })}
        <button type="button" className="button" onClick={() => setPicking(true)}><Plus size={14} aria-hidden="true" /> Add an exercise</button>
        <textarea className="field" rows={2} placeholder="Notes (how it felt, the gym, anything)" aria-label="Workout notes" value={s.note ?? ""} onChange={(e) => update({ ...s, note: e.target.value })} />
        <button type="button" className="icon-link" style={{ alignSelf: "flex-start" }} onClick={discard}>
          <Trash2 size={14} aria-hidden="true" /> Discard
        </button>
      </div>
      {rest && (
        <div className="gym-rest" role="timer" aria-label="Rest">
          <Timer size={16} aria-hidden="true" />
          <span className="gym-rest__time">{Math.max(0, Math.ceil((rest.until - Date.now()) / 1000))} s</span>
          <span className="gym-rest__bar"><span style={{ width: `${Math.max(0, (rest.until - Date.now()) / (rest.total * 1000)) * 100}%` }} /></span>
          <button type="button" className="chip chip--button" onClick={() => { const left = Math.ceil((rest.until - Date.now()) / 1000) + 15; setRest({ ...rest, until: rest.until + 15_000, total: rest.total + 15 }); gym.rest(left, "").catch(() => {}); }}>+15</button>
          <button type="button" className="chip chip--button" onClick={stopRest}>Skip</button>
        </div>
      )}
      {picking && g && (
        <ExercisePicker exercises={g.exercises} onClose={() => setPicking(false)}
          onPick={(ex) => { update({ ...s, entries: [...s.entries, { exercise: ex.id, sets: [{ weight: null, reps: null, done: false, type: "normal" }] }] }); setPicking(false); }} />
      )}
      {swapping != null && s.entries[swapping] && (
        <SwapSheet exercise={s.entries[swapping].exercise} gymId={s.gym ?? null} onClose={() => setSwapping(null)}
          onPick={(id, weight) => {
            update({ ...s, entries: s.entries.map((e, i) => (i === swapping ? { ...e, exercise: id, sets: e.sets.map((x) => (x.done ? x : { ...x, weight: x.type === "warmup" ? null : weight, reps: null })) } : e)) });
            setSwapping(null);
          }} />
      )}
      {openEx && <ExerciseSheet id={openEx} unit={unit} onClose={() => setOpenEx(null)} />}
    </>
  );
}

function SetTable({ ex, sets, last, unit, settings, onChange, onRemove }: {
  ex?: Exercise; sets: SetLog[]; last: SetLog[]; unit: string; settings?: { bar: number; plates: number[] };
  onChange: (i: number, patch: Partial<SetLog>) => void; onRemove: (i: number) => void;
}) {
  const kind = ex?.kind ?? "weight";
  const [platesFor, setPlatesFor] = useState<number | null>(null);
  // "Last" lines up with working sets only: last time's list leaves warm-ups out, and today's has them first.
  let n = 0, working = 0;
  return (
    <div className="gym-sets" role="table" aria-label="Sets">
      <div className="gym-sets__row gym-sets__head" role="row">
        <span>Set</span><span>Last</span>
        {kind === "weight" || kind === "bodyweight" ? <><span>{kind === "bodyweight" ? `+${unit}` : unit}</span><span>Reps</span></> : kind === "time" ? <><span /><span>Secs</span></> : <><span>Min</span><span>km</span></>}
        <span aria-label="Done" />
      </div>
      {sets.map((x, i) => {
        const label = x.type === "warmup" ? "W" : x.type === "drop" ? "D" : String(++n);
        const prev = x.type === "warmup" ? undefined : last[working++];
        const est = e1rm(x.weight, x.reps);
        return (
          <div key={i} className={`gym-sets__row ${x.done ? "gym-sets__row--done" : ""}`} role="row">
            <button type="button" className="gym-sets__type" title="Normal, warm-up or drop set" aria-label={`Set ${label}: change type`}
              onClick={() => onChange(i, { type: x.type === "normal" ? "warmup" : x.type === "warmup" ? "drop" : "normal" })}>{label}</button>
            <span className="muted gym-sets__prev">{prev ? (prev.weight ? `${prev.weight}×${prev.reps ?? "–"}` : prev.seconds ? `${prev.seconds}s` : `${prev.reps ?? "–"}`) : "–"}</span>
            {kind === "weight" || kind === "bodyweight" ? (
              <>
                <input className="field gym-sets__in" inputMode="decimal" aria-label={`Set ${label} weight`} value={x.weight ?? ""} placeholder={prev?.weight ? String(prev.weight) : kind === "bodyweight" ? "0" : ""}
                  onFocus={() => kind === "weight" && ex?.equipment === "barbell" && setPlatesFor(i)} onChange={(e) => onChange(i, { weight: e.target.value === "" ? null : Number(e.target.value) })} />
                <input className="field gym-sets__in" inputMode="numeric" aria-label={`Set ${label} reps`} value={x.reps ?? ""} placeholder={prev?.reps ? String(prev.reps) : ""}
                  onChange={(e) => onChange(i, { reps: e.target.value === "" ? null : Number(e.target.value) })} />
              </>
            ) : kind === "time" ? (
              <><span /><input className="field gym-sets__in" inputMode="numeric" aria-label={`Set ${label} seconds`} value={x.seconds ?? ""} onChange={(e) => onChange(i, { seconds: e.target.value === "" ? null : Number(e.target.value) })} /></>
            ) : (
              <>
                <input className="field gym-sets__in" inputMode="decimal" aria-label={`Set ${label} minutes`} value={x.seconds != null ? x.seconds / 60 : ""} onChange={(e) => onChange(i, { seconds: e.target.value === "" ? null : Math.round(Number(e.target.value) * 60) })} />
                <input className="field gym-sets__in" inputMode="decimal" aria-label={`Set ${label} km`} value={x.km ?? ""} onChange={(e) => onChange(i, { km: e.target.value === "" ? null : Number(e.target.value) })} />
              </>
            )}
            <button type="button" className={`gym-sets__done ${x.done ? "gym-sets__done--on" : ""}`} aria-pressed={x.done} aria-label={`Set ${label} done`}
              onClick={() => {
                const fill: Partial<SetLog> = { done: !x.done, at: !x.done ? new Date().toISOString() : null };
                if (!x.done && x.weight == null && prev?.weight) fill.weight = prev.weight;
                if (!x.done && x.reps == null && prev?.reps) fill.reps = prev.reps;
                onChange(i, fill);
              }}><Check size={16} aria-hidden="true" /></button>
            {x.done && x.type !== "warmup" && (
              <button type="button" className="chip chip--button gym-rpe" aria-label={`Set ${label} effort (RPE)`} title="How hard: RPE 6 (easy) to 10 (nothing left)"
                onClick={() => onChange(i, { rpe: x.rpe == null ? 7 : x.rpe >= 10 ? null : x.rpe + 1 })}>{x.rpe != null ? `RPE ${x.rpe}` : "RPE"}</button>
            )}
            {platesFor === i && x.weight && settings && (
              <span className="gym-sets__plates muted">
                {(() => { const p = plates(x.weight, settings.bar, settings.plates); return p.perSide.length ? `Each side: ${p.perSide.join(" + ")}${p.left ? ` (${p.left} short)` : ""}` : `The bar is ${settings.bar}`; })()}
                {est ? ` · est. 1RM ${kg(est, unit)}` : ""}
                <button type="button" className="icon-link" aria-label="Remove the set" onClick={() => onRemove(i)}><Trash2 size={12} aria-hidden="true" /></button>
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function Finished({ done, unit }: { done: { summary?: Summary; records?: GymRecord[]; offline?: boolean }; unit: string }) {
  const s = done.summary;
  return (
    <Glass className="widget" style={{ marginTop: 16, minHeight: 0 }} aria-label="Workout done">
      <header className="widget__head"><Trophy aria-hidden="true" /><span>Done</span></header>
      {done.offline ? (
        <p style={{ margin: 0 }}>Saved on this phone: it goes to SirisOS as soon as there's signal.</p>
      ) : s && (
        <>
          <h2 className="sheet__title" style={{ margin: 0 }}>{s.title}</h2>
          <div className="metrics">
            <div><div className="metric__value">{s.minutes ?? "–"}</div><div className="metric__label">Minutes</div></div>
            <div><div className="metric__value">{s.sets}</div><div className="metric__label">Sets</div></div>
            <div><div className="metric__value">{Math.round(s.volume).toLocaleString()}</div><div className="metric__label">Volume ({unit})</div></div>
          </div>
          {(done.records ?? []).length > 0 && (
            <ul className="items" aria-label="Records">
              {done.records!.map((r) => <li key={r.text} className="item"><Trophy size={16} className="tone-warning" aria-hidden="true" /><span className="item__text"><span className="item__title">{r.text}</span></span></li>)}
            </ul>
          )}
        </>
      )}
      <Link to="/gym" className="button button--primary" style={{ alignSelf: "flex-start" }}>Back to the gym</Link>
    </Glass>
  );
}


/** Swap an exercise mid-workout (6.93): the same movement first, then the same muscle, with last time and what to lift. */
function SwapSheet({ exercise, gymId, onPick, onClose }: { exercise: string; gymId: string | null; onPick: (id: string, weight: number | null) => void; onClose: () => void }) {
  const res = useResource(`gym:swap:${exercise}:${gymId ?? ""}`, () => gym.swap(exercise, gymId), {});
  return (
    <Sheet label="Swap the exercise" onClose={onClose}>
      <div className="stack" style={{ gap: 8 }}>
        <h2 className="sheet__title">Swap for</h2>
        {!res.data && <div className="skeleton" style={{ height: 120 }} />}
        <ul className="items">
          {(res.data?.options ?? []).map((o) => (
            <li key={o.id} className="item">
              <button type="button" className="item__text house__pick" onClick={() => onPick(o.id, o.weight)}>
                <span className="item__title">{o.name}</span>
                <span className="item__subtitle">{o.same_pattern ? "same movement" : "same muscle"} · {o.equipment}{o.last.length ? ` · last ${o.last.map((x) => `${x.weight ?? "bw"}×${x.reps ?? "–"}`).join(", ")}` : ""}{o.weight ? ` · try ${o.weight} kg` : ""}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </Sheet>
  );
}
