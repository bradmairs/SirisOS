import { useState, type FormEvent } from "react";
import { Check, ChevronLeft, ChevronRight, Minus, Plus, Target, Trash2 } from "lucide-react";
import { useResource } from "../api/resource";
import { goals, KIND_LABEL, type GoalKind, type YearGoal } from "../api/goals";
import { Glass } from "../components/Glass";

const STATE: Record<YearGoal["state"], { label: string; tone: string }> = {
  done: { label: "Done", tone: "tone-good" },
  on_track: { label: "On track", tone: "tone-good" },
  behind: { label: "Behind", tone: "tone-warning" },
  open: { label: "Not yet", tone: "muted" },
  unknown: { label: "No data yet", tone: "muted" },
};

const num = (v: number) => (Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 1 }));

/** The year's goals, set each January (4.4). Running, CPD, journal and tasks count themselves. */
export function GoalsCard({ thisYear }: { thisYear: number }) {
  const [year, setYear] = useState(thisYear);
  const { data, reload, error } = useResource(`goals:${year}`, () => goals.get(year), { staleMs: 5 * 60_000, persist: year === thisYear });
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function run(work: () => Promise<unknown>) {
    setBusy(true);
    setProblem(null);
    try {
      await work();
      await reload(true);
    } catch (e) {
      setProblem(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const list = data?.goals ?? [];
  const showForm = adding || (data?.set_them ?? false);
  return (
    <Glass as="section" className="widget goals" style={{ minHeight: 0 }} aria-label={`${year} goals`}>
      <header className="widget__head">
        <Target aria-hidden="true" /><span>{year} goals</span>
        <span className="row" style={{ marginLeft: "auto", gap: 2 }}>
          <button type="button" className="icon-link" aria-label="Previous year" onClick={() => setYear((y) => y - 1)}><ChevronLeft size={16} aria-hidden="true" /></button>
          <button type="button" className="icon-link" aria-label="Next year" disabled={year > thisYear} onClick={() => setYear((y) => y + 1)}><ChevronRight size={16} aria-hidden="true" /></button>
        </span>
      </header>
      {error && !data && <p className="tone-critical" role="alert" style={{ margin: 0 }}>{error}</p>}
      {data?.set_them && <p style={{ margin: 0 }}>A new year: what do you want to achieve in {year}? Running, CPD, journal and task goals keep count for you.</p>}
      {data && list.length === 0 && !data.set_them && <p className="muted" style={{ margin: 0, fontSize: 14 }}>No goals for {year}{year === thisYear ? " yet" : ""}.</p>}
      {list.length > 0 && (
        <>
          {year === thisYear && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{data!.through_year}% of the way through {year}.</p>}
          <ul className="items goals__list">
            {list.map((g) => <GoalRow key={g.id} goal={g} busy={busy} through={year === thisYear ? data!.through_year : 100}
              onChange={(c) => run(() => goals.change(year, g.id, c))} onRemove={() => run(() => goals.remove(year, g.id))} />)}
          </ul>
        </>
      )}
      {showForm ? <NewGoal year={year} busy={busy} onAdd={(g) => run(async () => { await goals.add(year, g); setAdding(false); })} onCancel={list.length ? () => setAdding(false) : undefined} />
        : <button type="button" className="button button--small" style={{ alignSelf: "flex-start" }} onClick={() => setAdding(true)}><Plus size={14} aria-hidden="true" /> Add a goal</button>}
      {problem && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 14 }}>{problem}</p>}
    </Glass>
  );
}

function GoalRow({ goal: g, busy, through, onChange, onRemove }: {
  goal: YearGoal; busy: boolean; through: number; onChange: (c: Partial<YearGoal>) => void; onRemove: () => void;
}) {
  const state = STATE[g.state];
  const amount = g.kind === "done" ? null : `${g.value == null ? "–" : num(g.value)} of ${num(g.target ?? 0)}${g.unit ? ` ${g.unit}` : ""}`;
  return (
    <li className="item goal">
      {g.kind === "done" ? (
        <button type="button" className={`icon-link goal__check ${g.done ? "goal__check--on" : ""}`} disabled={busy} aria-pressed={g.done}
          aria-label={g.done ? `Mark "${g.title}" not done` : `Mark "${g.title}" done`} onClick={() => onChange({ done: !g.done })}>
          <Check size={15} aria-hidden="true" />
        </button>
      ) : <Target size={16} className="muted" aria-hidden="true" />}
      <span className="item__text">
        <div className="item__title">{g.title}</div>
        <div className="item__subtitle">
          <span className={state.tone}>{state.label}</span>
          {amount && <> · {amount}</>}
        </div>
        {g.kind !== "done" && g.percent != null && (
          <div className="goal__bar" role="img" aria-label={`${g.percent}% there`}>
            <span className={`goal__fill goal__fill--${g.state}`} style={{ width: `${g.percent}%` }} />
            {through < 100 && <span className="goal__mark" style={{ left: `${through}%` }} title="Where you'd be at an even pace" />}
          </div>
        )}
      </span>
      {g.kind === "count" && (
        <span className="row" style={{ gap: 2 }}>
          <button type="button" className="icon-link" disabled={busy || g.progress <= 0} aria-label={`One less for "${g.title}"`} onClick={() => onChange({ progress: Math.max(0, g.progress - 1) })}><Minus size={15} aria-hidden="true" /></button>
          <button type="button" className="icon-link" disabled={busy} aria-label={`One more for "${g.title}"`} onClick={() => onChange({ progress: g.progress + 1 })}><Plus size={15} aria-hidden="true" /></button>
        </span>
      )}
      <button type="button" className="icon-link" disabled={busy} aria-label={`Remove "${g.title}"`} onClick={() => window.confirm(`Remove "${g.title}"?`) && onRemove()}>
        <Trash2 size={14} aria-hidden="true" />
      </button>
    </li>
  );
}

function NewGoal({ year, busy, onAdd, onCancel }: { year: number; busy: boolean; onAdd: (g: { title: string; kind: GoalKind; target?: number | null; unit?: string }) => void; onCancel?: () => void }) {
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<GoalKind>("done");
  const [target, setTarget] = useState("");
  const [unit, setUnit] = useState("");
  const needsTarget = kind !== "done";
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim() || (needsTarget && !(Number(target) > 0))) return;
    onAdd({ title: title.trim(), kind, target: needsTarget ? Number(target) : null, ...(kind === "count" && unit.trim() ? { unit: unit.trim() } : {}) });
  }
  return (
    <form className="goals__form" onSubmit={submit} aria-label={`New goal for ${year}`}>
      <input className="field" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Run 1,000 km" aria-label="Goal" />
      <select className="field" value={kind} onChange={(e) => setKind(e.target.value as GoalKind)} aria-label="How it's tracked">
        {(Object.keys(KIND_LABEL) as GoalKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
      </select>
      {needsTarget && (
        <div className="row" style={{ gap: 6 }}>
          <input className="field" type="number" inputMode="decimal" min="0" step="any" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="Target" aria-label="Target" />
          {kind === "count" && <input className="field" value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="Unit, e.g. books" aria-label="Unit" />}
        </div>
      )}
      <div className="row" style={{ gap: 6 }}>
        <button type="submit" className="button button--small button--primary" disabled={busy || !title.trim() || (needsTarget && !(Number(target) > 0))}>Add goal</button>
        {onCancel && <button type="button" className="button button--small" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}
