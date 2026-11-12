import { useMemo, useState } from "react";
import { CalendarDays, Flame, Upload } from "lucide-react";
import { useResource } from "../api/resource";
import { gym, type Gym, type ImportPreview, type ImportUnit } from "../api/gym";
import { Glass } from "../components/Glass";
import { fmtDay } from "./GymShared";
import { RecentList } from "./GymToday";

/** SirisGym's History tab and the importer (split out of Gym.tsx in 8.9). */

export function HistoryView({ g, onChange }: { g: Gym; onChange: () => void }) {
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
export function HeatmapCard() {
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

export const HOW: Record<ImportPreview["exercises"][number]["how"], string> = { exact: "same name", close: "same exercise", guess: "best guess, check it", none: "no match" };

/** Bring years of JEFIT (or any app's CSV) in: preview, check what each exercise maps to, then import. Importing again replaces those days. */
export function ImportCard({ g, onDone }: { g: Gym; onDone: () => void }) {
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
