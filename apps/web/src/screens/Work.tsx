import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Award, BriefcaseBusiness, Check, ListTodo, NotebookPen, Ruler, Search } from "lucide-react";
import { brain } from "../api/hub";
import { useResource } from "../api/resource";
import { tasks, type TaskItem } from "../api/tasks";
import type { BrainHit } from "../api/types";
import { span, work, type WorkDay } from "../api/work";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";

const GROUPS = [["overdue", "Overdue"], ["today", "Today"], ["week", "This week"]] as const;

export function useWork() {
  return useResource<WorkDay>("work", () => work.get(), { staleMs: 60_000, refreshMs: 5 * 60_000, persist: true });
}

function lead(w: WorkDay): string {
  if (w.hours.on && w.hours.minutes_left != null) return `Home time in ${span(w.hours.minutes_left)} (${w.hours.end})`;
  return w.hours.workday ? `Work hours ${w.hours.start} to ${w.hours.end}` : "Not a work day";
}

/** Work (7.2): everything for the working day at the engineering job, open from 8:00 to 4:30. */
export function WorkScreen() {
  const res = useWork();
  useEffect(() => { document.title = "Work · SirisOS"; }, []);
  const w = res.data;
  return (
    <>
      <PageHead eyebrow={w ? lead(w) : "Work"} title="Work" />
      {!w && res.error && <div className="error-banner" role="alert">{res.error}</div>}
      {!w && !res.error && <div className="skeleton" style={{ height: 220, marginTop: 16 }} aria-busy="true" />}
      {w && (
        <div className="stack" style={{ marginTop: 16 }}>
          <WorkTasksCard w={w} onChange={() => res.reload?.(true)} />
          <TodosCard w={w} onChange={() => res.reload?.(true)} />
          <WorkNotesCard />
          <ToolsCard w={w} />
        </div>
      )}
    </>
  );
}

function WorkTasksCard({ w, onChange }: { w: WorkDay; onChange: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [gone, setGone] = useState<Set<string>>(new Set());
  const done = async (t: TaskItem) => {
    setBusy(t.id);
    try { await tasks.done(t); setGone((g) => new Set(g).add(t.id)); onChange(); } finally { setBusy(null); }
  };
  const add = async () => {
    if (!text.trim()) return;
    await tasks.add({ text: text.trim(), area: "work" });
    setText("");
    onChange();
  };
  const total = GROUPS.reduce((n, [g]) => n + (w.tasks.groups[g]?.filter((t) => !gone.has(t.id)).length ?? 0), 0);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Work tasks">
      <header className="widget__head"><ListTodo aria-hidden="true" /><span>Work tasks</span><Link to="/tasks" className="widget__source">All tasks</Link></header>
      {total === 0 && <p className="muted" style={{ margin: 0 }}>Nothing due this week.</p>}
      {GROUPS.map(([g, label]) => {
        const items = (w.tasks.groups[g] ?? []).filter((t) => !gone.has(t.id));
        return items.length ? (
          <div key={g}>
            <p className={`work-group ${g === "overdue" ? "tone-warning" : "muted"}`}>{label}</p>
            <ul className="items">
              {items.map((t) => (
                <li key={t.id} className="item">
                  <button type="button" className="icon-link" aria-label={`Done: ${t.title}`} disabled={busy === t.id} onClick={() => done(t)}><Check size={16} aria-hidden="true" /></button>
                  <span className="item__text"><span className="item__title">{t.title}</span>
                    {(t.time || t.detail) && <span className="item__subtitle">{[t.time, t.detail].filter(Boolean).join(" · ")}</span>}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null;
      })}
      <form className="row" style={{ gap: 8 }} onSubmit={(e) => { e.preventDefault(); void add(); }}>
        <input className="field" style={{ flex: 1 }} placeholder="Add a work task (e.g. send RFI tomorrow)" aria-label="New work task" value={text} onChange={(e) => setText(e.target.value)} />
        <button type="submit" className="button" disabled={!text.trim()}>Add</button>
      </form>
    </Glass>
  );
}

function TodosCard({ w, onChange }: { w: WorkDay; onChange: () => void }) {
  const [gone, setGone] = useState<Set<string>>(new Set());
  const items = (w.todos ?? []).filter((t) => !gone.has(`${t.note}|${t.task}`));
  if (!w.todos?.length) return null;
  const done = async (t: { note: string; task: string }) => {
    await brain.done(t.note, t.task);
    setGone((g) => new Set(g).add(`${t.note}|${t.task}`));
    onChange();
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="To-dos in work notes">
      <header className="widget__head"><NotebookPen aria-hidden="true" /><span>To-dos in work notes</span></header>
      <ul className="items">
        {items.map((t) => (
          <li key={`${t.note}|${t.task}`} className="item">
            <button type="button" className="icon-link" aria-label={`Done: ${t.task}`} onClick={() => done(t)}><Check size={16} aria-hidden="true" /></button>
            <span className="item__text"><span className="item__title">{t.task}</span>
              <span className="item__subtitle"><Link to={`/brain?q=${encodeURIComponent(t.note)}`}>{t.note}</Link>{t.due ? ` · due ${t.due}` : ""}</span></span>
          </li>
        ))}
      </ul>
    </Glass>
  );
}

/** Find a work note, or jot one down: it's tagged #work, so the nightly sort files it under Work/. */
function WorkNotesCard() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<BrainHit[] | null>(null);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  useEffect(() => {
    const query = q.trim();
    if (!query) { setHits(null); return; }
    const t = window.setTimeout(() => {
      brain.search(query, 20).then((all) => setHits(all.filter((h) => (h.path ?? "").startsWith("Work/")).slice(0, 8))).catch(() => setHits([]));
    }, 300);
    return () => window.clearTimeout(t);
  }, [q]);
  const save = async () => {
    const r = await brain.capture({ text: note.trim(), tags: ["work"] });
    setSaved(`Saved to Siris as “${r.title}”.`);
    setNote("");
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Work notes">
      <header className="widget__head"><Search aria-hidden="true" /><span>Work notes</span></header>
      <label className="mini-search">
        <Search size={14} aria-hidden="true" />
        <input placeholder="Search work notes (GVW, processes, contacts…)" aria-label="Search work notes" value={q} onChange={(e) => setQ(e.target.value)} />
      </label>
      {hits && (hits.length ? (
        <ul className="items">
          {hits.map((h) => (
            <li key={h.title} className="item"><span className="item__text"><Link className="item__title" to={`/brain?q=${encodeURIComponent(h.title)}`}>{h.title}</Link>
              {h.excerpts?.[0] && <span className="item__subtitle">{h.excerpts[0]}</span>}</span></li>
          ))}
        </ul>
      ) : <p className="muted" style={{ margin: 0 }}>No work notes match.</p>)}
      <textarea className="field" rows={2} placeholder="Jot something down for work (filed under Work/ tonight)" aria-label="Work note" value={note} onChange={(e) => { setNote(e.target.value); setSaved(null); }} />
      <button type="button" className="button" style={{ alignSelf: "flex-start" }} disabled={!note.trim()} onClick={save}>Save to Siris</button>
      {saved && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{saved}</p>}
    </Glass>
  );
}

function ToolsCard({ w }: { w: WorkDay }) {
  const c = w.cpd;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Engineering">
      <header className="widget__head"><Ruler aria-hidden="true" /><span>Engineering</span></header>
      {w.engineering.current && <p style={{ margin: 0 }}>Working on <strong>{w.engineering.current.name}</strong> <span className="muted">({w.engineering.current.kind})</span></p>}
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <Link to="/engineering" className="button"><Ruler size={14} aria-hidden="true" /> Calculators</Link>
        <Link to="/career" className="button"><Award size={14} aria-hidden="true" /> Career and CPD</Link>
      </div>
      {c && (
        <div aria-label="CPD">
          <p className="muted" style={{ margin: "0 0 4px", fontSize: 13 }}>CPD: {c.total} of {c.required} hours in the last three years{c.short > 0 ? `, ${c.short} to go` : ", done"}.</p>
          <span className="work-bar"><span style={{ width: `${Math.min(100, (c.total / Math.max(1, c.required)) * 100)}%` }} /></span>
        </div>
      )}
    </Glass>
  );
}

/** On Home in work hours (7.2): what's due and the way into Work (no calendar or projects: 7.31). */
export function WorkHomeCard() {
  const res = useWork();
  const w = res.data;
  if (!w || !w.hours.on) return null;
  const due = (w.tasks.counts.overdue ?? 0) + (w.tasks.counts.today ?? 0);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0, marginTop: 14 }} aria-label="At work">
      <header className="widget__head"><BriefcaseBusiness aria-hidden="true" /><span>At work</span>
        {w.hours.minutes_left != null && <span className="widget__source">home in {span(w.hours.minutes_left)}</span>}</header>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        {due ? `${due} work task${due === 1 ? "" : "s"} due` : "No work tasks due today"}{w.todos?.length ? ` · ${w.todos.length} to-do${w.todos.length === 1 ? "" : "s"} in work notes` : ""}
      </p>
      <Link to="/work" className="button button--primary" style={{ alignSelf: "flex-start" }}>Open Work</Link>
    </Glass>
  );
}
