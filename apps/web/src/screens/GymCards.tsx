import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Archive, Bandage, Compass, Download, Dumbbell, HeartPulse, Trash2, Video as VideoIcon } from "lucide-react";
import { AREAS, gym, loadActive, type Area, type Backup, type Fitness, type Niggle, type Routine, type Video } from "../api/gym";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";
import { gymTime } from "../components/Dock";

/** The week's one or two changes (7.0), from SirisAI: training, sleep, recovery and protein together. */
export function GymCoachCard() {
  const res = useResource("gym:coach", () => gym.coach(), { staleMs: 30 * 60_000, persist: true });
  const c = res.data;
  if (!c?.changes?.length) return null;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="This week's coach">
      <header className="widget__head"><Compass aria-hidden="true" /><span>{c.changes.length === 1 ? "One change this week" : `${c.changes.length} changes this week`}</span></header>
      <ul className="items">
        {c.changes.map((x) => (
          <li key={x.title} className="item"><span className="item__text"><span className="item__title">{x.title}</span><span className="item__subtitle">{x.why}</span></span></li>
        ))}
      </ul>
    </Glass>
  );
}

/** One card from 6 to 8 am (7.0): today's workout, readiness, and one tap to start it and the Watch's Shortcut. */
export function MorningGymCard({ at = new Date() }: { at?: Date }) {
  const navigate = useNavigate();
  const on = gymTime(at);
  const res = useResource("gym:morning", () => gym.morning(), { staleMs: 5 * 60_000, enabled: on });
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const m = res.data;
  if (!on || !m?.plan || m.plan.done || m.plan.rest) return null;
  const going = loadActive();
  const start = async () => {
    setBusy(true);
    setFailed(null);
    try {
      const { startWorkout } = await import("./Gym");
      await startWorkout(navigate, { id: m.routine } as Routine, m.day, m.gym, m.shortcut);
    } catch (e) {
      setFailed(e instanceof Error ? e.message : "Couldn't start it.");
    } finally { setBusy(false); }
  };
  const lifts = m.plan.lifts ?? [];
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0, marginTop: 14 }} aria-label="Today's gym plan">
      <header className="widget__head"><Dumbbell aria-hidden="true" /><span>Gym this morning</span>{m.readiness?.band && <span className="widget__source">Readiness {m.readiness.score ?? ""} · {m.readiness.band}</span>}</header>
      <p style={{ margin: 0, fontSize: 16 }}><strong>{m.plan.title}</strong></p>
      {m.plan.note && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{m.plan.note}</p>}
      {lifts.length > 0 && (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          {lifts.map((l) => `${l.name} ${l.sets} × ${l.reps}${l.weight ? ` at ${l.weight} kg` : ""}`).join(" · ")}{m.plan.more ? ` · and ${m.plan.more} more` : ""}
        </p>
      )}
      {going ? (
        <Link to="/gym/workout" className="button button--primary" style={{ alignSelf: "flex-start" }}>Carry on</Link>
      ) : (
        <button type="button" className="button button--primary" style={{ alignSelf: "flex-start" }} disabled={busy} onClick={start}>{m.shortcut ? "Start it and the Watch" : "Start it"}</button>
      )}
      {failed && <p role="alert" className="tone-warning" style={{ margin: 0, fontSize: 13 }}>{failed}</p>}
    </Glass>
  );
}

/** Sore spots (7.1): exercises that load one are swapped out of plans until it's marked healed. */
export function NigglesCard({ niggles, onChange }: { niggles: Niggle[]; onChange: () => void }) {
  const [adding, setAdding] = useState(false);
  const [area, setArea] = useState<Area>("shoulder");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const add = async () => { setBusy(true); try { await gym.addNiggle(area, note.trim()); setAdding(false); setNote(""); onChange(); } finally { setBusy(false); } };
  const heal = async (id: string) => { await gym.healNiggle(id); onChange(); };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Niggles">
      <header className="widget__head"><Bandage aria-hidden="true" /><span>{niggles.length ? "Sparing" : "Niggles"}</span></header>
      {niggles.length > 0 ? (
        <ul className="items">
          {niggles.map((n) => (
            <li key={n.id} className="item">
              <span className="item__text"><span className="item__title">Sore {n.area}</span>
                <span className="item__subtitle">Since {n.started}{n.note ? ` · ${n.note}` : ""}. Exercises that load it are swapped out of your plans.</span></span>
              <button type="button" className="chip chip--button" onClick={() => heal(n.id)}>Healed</button>
            </li>
          ))}
        </ul>
      ) : !adding && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Something sore? Tell SirisGym and it swaps out what loads it until it's healed.</p>}
      {adding ? (
        <>
          <div className="row gym-chips" role="radiogroup" aria-label="Where">
            {AREAS.map((a) => <button key={a} type="button" role="radio" aria-checked={area === a} className={`chip chip--button ${area === a ? "chip--active" : ""}`} onClick={() => setArea(a)}>{a}</button>)}
          </div>
          <input className="field" placeholder="What happened (optional)" aria-label="Note" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
          <div className="row" style={{ gap: 8 }}>
            <button type="button" className="button button--primary" disabled={busy} onClick={add}>Spare my {area}</button>
            <button type="button" className="button" onClick={() => setAdding(false)}>Cancel</button>
          </div>
        </>
      ) : <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => setAdding(true)}>Something's sore</button>}
    </Glass>
  );
}

/** Fitter at the same weight (7.1): the Watch's peak heart rate at the weight you've lifted most, first time to latest. */
export function FitnessLine({ f }: { f: Fitness }) {
  return (
    <p className={`gym-fitness ${f.verdict === "fitter" ? "tone-good" : f.verdict === "harder" ? "tone-warning" : "muted"}`} style={{ margin: 0, fontSize: 13 }}>
      <HeartPulse size={14} aria-hidden="true" /> {f.text} <span className="muted">({f.times} times with the Watch)</span>
    </p>
  );
}

/** Film a set (7.1): the video is kept on your server with the exercise, set, weight and reps. */
export function FilmButton({ exercise, session, set, weight, reps, name }: { exercise: string; session?: string; set?: number; weight?: number | null; reps?: number | null; name: string }) {
  const [state, setState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const [err, setErr] = useState("");
  const up = async (f: File | undefined) => {
    if (!f) return;
    setState("busy");
    try { await gym.addVideo(f, { exercise, session, set, weight, reps }); setState("done"); } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't save it."); setState("error"); }
  };
  return (
    <label className="chip chip--button" title={err || "Film a set to check your form"} aria-disabled={state === "busy"}>
      <VideoIcon size={12} aria-hidden="true" /> {state === "busy" ? "Saving…" : state === "done" ? "Filmed" : state === "error" ? "Didn't save" : "Film"}
      <input type="file" accept="video/*" capture="environment" hidden aria-label={`Film a set of ${name}`} onChange={(e) => up(e.target.files?.[0])} />
    </label>
  );
}

/** Form videos for an exercise (7.1): pick two to watch side by side. */
export function VideosCard({ videos, onChange }: { videos: Video[]; onChange: () => void }) {
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [pair, setPair] = useState<string[]>(() => videos.slice(0, 2).map((v) => v.id));
  useEffect(() => {
    let alive = true;
    for (const id of pair) if (!urls[id]) gym.videoUrl(id).then((u) => { if (alive) setUrls((x) => ({ ...x, [id]: u })); }).catch(() => {});
    return () => { alive = false; };
  }, [pair.join()]);  // eslint-disable-line react-hooks/exhaustive-deps
  if (!videos.length) return <p className="muted" style={{ margin: 0, fontSize: 13 }}>No form videos yet: tap Film on this exercise during a workout.</p>;
  const label = (v: Video) => `${v.date}${v.weight ? ` · ${v.weight} kg` : ""}${v.reps ? ` × ${v.reps}` : ""}${v.set ? ` (set ${v.set})` : ""}`;
  const pick = (id: string) => setPair((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-2)));
  return (
    <div className="stack" style={{ gap: 8 }} aria-label="Form videos">
      <div className="gym-compare">
        {pair.map((id) => {
          const v = videos.find((x) => x.id === id);
          return v ? (
            <figure key={id}>
              {urls[id] ? <video src={urls[id]} controls playsInline muted preload="metadata" aria-label={label(v)} /> : <div className="skeleton" style={{ aspectRatio: "9/16" }} />}
              <figcaption className="muted" style={{ fontSize: 12 }}>{label(v)}</figcaption>
            </figure>
          ) : null;
        })}
      </div>
      <ul className="items">
        {videos.map((v) => (
          <li key={v.id} className="item">
            <label className="row" style={{ gap: 8, flex: 1 }}><input type="checkbox" checked={pair.includes(v.id)} onChange={() => pick(v.id)} aria-label={`Compare ${label(v)}`} />
              <span className="item__text"><span className="item__title">{label(v)}</span>{v.note && <span className="item__subtitle">{v.note}</span>}</span></label>
            <button type="button" className="icon-link" aria-label={`Delete the video from ${v.date}`}
              onClick={async () => { if (window.confirm("Delete this video?")) { await gym.deleteVideo(v.id); setPair((p) => p.filter((x) => x !== v.id)); onChange(); } }}><Trash2 size={14} aria-hidden="true" /></button>
          </li>
        ))}
      </ul>
    </div>
  );
}

const TAGS: Record<string, string> = { "before-cleanup": "Before the tidy of empty exercises", "before-local-times": "Before imported times moved to local time",
  "before-titles": "Before imported workouts were renamed", "before-restore": "Before a restore", "before-merge": "Before merging exercises" };

/** The copies of your gym data saved before each one-off change (7.1), to put back, and every set to download. */
export function BackupsCard({ onChange }: { onChange: () => void }) {
  const res = useResource("gym:backups", () => gym.backups(), { staleMs: 0 });
  const [msg, setMsg] = useState<string | null>(null);
  const restore = async (b: Backup) => {
    if (!window.confirm(`Put back the copy from ${new Date(b.saved_at).toLocaleString()}? Your gym data as it is now is saved first, so you can undo this.`)) return;
    const r = await gym.restore(b.name);
    setMsg(`Restored: ${r.sessions} workouts. The data from before is kept as a backup too.`);
    res.reload?.(true);
    onChange();
  };
  const list = res.data?.backups ?? [];
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Backups and export">
      <header className="widget__head"><Archive aria-hidden="true" /><span>Backups and export</span></header>
      {list.length ? (
        <ul className="items">
          {list.slice(0, 8).map((b) => (
            <li key={b.name} className="item">
              <span className="item__text"><span className="item__title">{TAGS[b.tag] ?? b.tag.replace(/-/g, " ")}</span>
                <span className="item__subtitle">{new Date(b.saved_at).toLocaleString()}{b.sessions != null ? ` · ${b.sessions} workouts` : ""} · {Math.max(1, Math.round(b.bytes / 1024))} KB</span></span>
              <button type="button" className="chip chip--button" onClick={() => restore(b)}>Restore</button>
            </li>
          ))}
        </ul>
      ) : <p className="muted" style={{ margin: 0, fontSize: 13 }}>No backups yet. SirisGym saves one before any change it makes to your data on its own.</p>}
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="button" onClick={() => gym.download("csv")}><Download size={14} aria-hidden="true" /> Every set (CSV)</button>
        <button type="button" className="button" onClick={() => gym.download("json")}><Download size={14} aria-hidden="true" /> Everything (JSON)</button>
      </div>
      {msg && <p role="status" style={{ margin: 0 }}>{msg}</p>}
    </Glass>
  );
}
