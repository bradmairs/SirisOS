import { useEffect, useState } from "react";
import { Activity, Camera, CalendarDays, Plus, Ruler, Trash2, TrendingUp, Trophy } from "lucide-react";
import { useResource } from "../api/resource";
import { gym, type Measurement, type Photo } from "../api/gym";
import { DecimalInput } from "../components/DecimalInput";
import { Glass } from "../components/Glass";
import { fmtDay } from "./GymShared";

/** SirisGym's Progress tab (split out of Gym.tsx in 8.9). */

/** Working sets a month for each muscle (8.8): which are growing and which are slipping. */
export function MuscleTrendsCard() {
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

export const LEVEL_TONE: Record<string, string> = { "starting out": "", beginner: "", novice: "tone-good", intermediate: "tone-good", advanced: "tone-warning" };

/** Strength against bodyweight and the year in review (6.8). */
/** Body measurements against your weight (6.9). */
export function BodyCard() {
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
export function PhotosCard() {
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

export function ProgressView() {
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
