import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Award, BriefcaseBusiness, Calculator, Check, Clock, ExternalLink, ListTodo, NotebookPen, Pause, Play, RotateCcw, Search, Timer } from "lucide-react";
import { brain } from "../api/hub";
import { links, type LinkStatus } from "../api/links";
import { useResource } from "../api/resource";
import { tasks, type TaskItem } from "../api/tasks";
import type { BrainHit } from "../api/types";
import { dayFraction, span, work, type CpdCategory, type WorkDay } from "../api/work";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";

type Group = "overdue" | "today" | "week";
const GROUPS: [Group, string][] = [["overdue", "Overdue"], ["today", "Today"], ["week", "This week"]];

export function useWork() {
  return useResource<WorkDay>("work", () => work.get(), { staleMs: 60_000, refreshMs: 5 * 60_000, persist: true });
}

function lead(w: WorkDay): string {
  if (w.hours.on && w.hours.minutes_left != null) return `Home time in ${span(w.hours.minutes_left)} (${w.hours.end})`;
  return w.hours.workday ? `Work hours ${w.hours.start} to ${w.hours.end}` : "Not a work day";
}

/** "1h 15m", "45m": short enough for a tile. */
const short = (minutes: number) => {
  const m = Math.max(0, Math.round(minutes));
  return m >= 60 ? `${Math.floor(m / 60)}h${m % 60 ? ` ${m % 60}m` : ""}` : `${m}m`;
};

const clock = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}${m ? `:${String(m).padStart(2, "0")}` : ""} ${h < 12 ? "am" : "pm"}`;
};

/** Work (7.2; made visual in 7.4): the working day at the engineering job, open from 8:00 to 4:30. */
export function WorkScreen() {
  const res = useWork();
  useEffect(() => { document.title = "Work · SirisOS"; }, []);
  const w = res.data;
  const reload = () => res.reload?.(true);
  return (
    <>
      <PageHead eyebrow={w ? lead(w) : "Work"} title="Work" />
      {!w && res.error && <div className="error-banner" role="alert">{res.error}</div>}
      {!w && !res.error && <div className="skeleton" style={{ height: 220, marginTop: 16 }} aria-busy="true" />}
      {w && (
        <div className="work-grid">
          <DayCard w={w} />
          <FocusCard onLogged={reload} />
          <WorkTasksCard w={w} onChange={reload} />
          <WeekCard w={w} />
          <AppsCard w={w} />
          <CpdCard w={w} onChange={reload} />
          <TodosCard w={w} onChange={reload} />
          <WorkNotesCard w={w} />
        </div>
      )}
    </>
  );
}

/** A ring that fills from 0 to `value` (0-1), with whatever sits in its middle. */
function Ring({ value, size = 132, stroke = 12, label, children, tone = "accent" }: {
  value: number; size?: number; stroke?: number; label: string; children?: React.ReactNode; tone?: "accent" | "good" | "warning";
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.min(1, Math.max(0, value));
  return (
    <div className="work-ring" style={{ width: size, height: size }} role="img" aria-label={label}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} className="work-ring__track" strokeWidth={stroke} />
        {v > 0 && <circle cx={size / 2} cy={size / 2} r={r} className={`work-ring__fill work-ring__fill--${tone}`} strokeWidth={stroke}
          strokeDasharray={`${c * v} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />}
      </svg>
      <div className="work-ring__middle">{children}</div>
    </div>
  );
}

/** 1. The working day as a ring: how far through 8:00 to 4:30 it is, home time, and what's done. */
function DayCard({ w }: { w: WorkDay }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const t = window.setInterval(() => setNow(new Date()), 30_000); return () => window.clearInterval(t); }, []);
  const f = dayFraction(w.hours.start, w.hours.end, now);
  const left = Math.max(0, Math.round((1 - f) * ((+w.hours.end.slice(0, 2) * 60 + +w.hours.end.slice(3)) - (+w.hours.start.slice(0, 2) * 60 + +w.hours.start.slice(3)))));
  const wk = w.week;
  return (
    <Glass as="section" className="widget work-day" style={{ minHeight: 0 }} aria-label="The working day">
      <Ring value={f} size={148} stroke={14} label={`${Math.round(f * 100)}% of the working day done`}>
        {w.hours.workday && f < 1 ? (f > 0 ? <><strong className="work-ring__big">{span(left)}</strong><span className="muted">to home time</span></>
          : <><strong className="work-ring__big">{clock(w.hours.start)}</strong><span className="muted">start</span></>)
          : <><strong className="work-ring__big">{w.hours.workday ? "Done" : "Off"}</strong><span className="muted">{w.hours.workday ? "for today" : "not a work day"}</span></>}
      </Ring>
      <div className="work-day__side">
        <p className="work-day__hours"><Clock size={14} aria-hidden="true" /> {clock(w.hours.start)} to {clock(w.hours.end)}</p>
        <div className="work-stats">
          <div><span className="work-stats__n">{wk?.done_today ?? 0}</span><span className="work-stats__l">done today</span></div>
          <div><span className="work-stats__n">{short(wk?.focus_today ?? 0)}</span><span className="work-stats__l">focused</span></div>
          <div><span className="work-stats__n">{(w.tasks.counts.today ?? 0) + (w.tasks.counts.overdue ?? 0)}</span><span className="work-stats__l">still due</span></div>
        </div>
      </div>
    </Glass>
  );
}

/** 2. Work tasks: three tiles (overdue, today, this week) that pick the list, and a box to add one. */
function WorkTasksCard({ w, onChange }: { w: WorkDay; onChange: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [gone, setGone] = useState<Set<string>>(new Set());
  const counts = Object.fromEntries(GROUPS.map(([g]) => [g, (w.tasks.groups[g] ?? []).filter((t) => !gone.has(t.id)).length])) as Record<Group, number>;
  const [pick, setPick] = useState<Group>(() => (counts.overdue ? "overdue" : counts.today ? "today" : "week"));
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
  const items = (w.tasks.groups[pick] ?? []).filter((t) => !gone.has(t.id));
  return (
    <Glass as="section" className="widget work-tasks" style={{ minHeight: 0 }} aria-label="Work tasks">
      <header className="widget__head"><ListTodo aria-hidden="true" /><span>Work tasks</span><Link to="/tasks" className="widget__source">All tasks</Link></header>
      <div className="work-tiles" role="tablist" aria-label="Which tasks">
        {GROUPS.map(([g, label]) => (
          <button key={g} type="button" role="tab" aria-selected={pick === g} onClick={() => setPick(g)}
            className={`work-tile${pick === g ? " work-tile--on" : ""}${g === "overdue" && counts[g] ? " work-tile--late" : ""}`}>
            <span className="work-tile__n">{counts[g]}</span><span className="work-tile__l">{label}</span>
          </button>
        ))}
      </div>
      {items.length ? (
        <ul className="items">
          {items.map((t) => (
            <li key={t.id} className="item">
              <button type="button" className="icon-link" aria-label={`Done: ${t.title}`} disabled={busy === t.id} onClick={() => done(t)}><Check size={16} aria-hidden="true" /></button>
              <span className="item__text"><span className="item__title">{t.title}</span>
                {(t.time || t.detail) && <span className="item__subtitle">{[t.time, t.detail].filter(Boolean).join(" · ")}</span>}</span>
            </li>
          ))}
        </ul>
      ) : <p className="muted" style={{ margin: 0 }}>{pick === "overdue" ? "Nothing overdue." : pick === "today" ? "Nothing due today." : "Nothing else this week."}</p>}
      <form className="row" style={{ gap: 8 }} onSubmit={(e) => { e.preventDefault(); void add(); }}>
        <input className="field" style={{ flex: 1, minWidth: 0 }} placeholder="Add a work task (e.g. send RFI tomorrow)" aria-label="New work task" value={text} onChange={(e) => setText(e.target.value)} />
        <button type="submit" className="button" disabled={!text.trim()}>Add</button>
      </form>
    </Glass>
  );
}

/** 2b. This week: work done each day as bars, Monday to Friday (weekends when there was any). */
function WeekCard({ w }: { w: WorkDay }) {
  const days = (w.week?.days ?? []).filter((d, i) => i < 5 || d.done > 0 || d.focus_min > 0);
  if (!days.length) return null;
  const top = Math.max(1, ...days.map((d) => d.done));
  const today = w.date;
  const total = days.reduce((n, d) => n + d.done, 0);
  const focus = days.reduce((n, d) => n + d.focus_min, 0);
  return (
    <Glass as="section" className="widget work-week" style={{ minHeight: 0 }} aria-label="This week">
      <header className="widget__head"><Check aria-hidden="true" /><span>This week</span><span className="widget__source">{total} done{focus ? ` · ${span(focus)} focused` : ""}</span></header>
      <div className="work-bars" role="list" aria-label="Work done each day">
        {days.map((d) => (
          <div key={d.date} className={`work-bars__day${d.date === today ? " work-bars__day--today" : ""}`} role="listitem" tabIndex={0}
            title={`${d.weekday}: ${d.done} done${d.focus_min ? `, ${span(d.focus_min)} focused` : ""}`} aria-label={`${d.weekday}: ${d.done} done${d.focus_min ? `, ${span(d.focus_min)} focused` : ""}`}>
            <span className="work-bars__n">{d.done || ""}</span>
            <span className="work-bars__track"><span className="work-bars__bar" style={{ height: `${(d.done / top) * 100}%` }} /></span>
            <span className="work-bars__d">{d.weekday}</span>
          </div>
        ))}
      </div>
    </Glass>
  );
}

const FOCUS_KEY = "sirisos.work.focus";
type FocusState = { mode: "focus" | "break"; ends: number | null; left: number; sessions: number; day: string };
const LEN = { focus: 25 * 60, break: 5 * 60 };
const todayKey = () => new Date().toISOString().slice(0, 10);

function loadFocus(): FocusState {
  try {
    const s = JSON.parse(window.localStorage.getItem(FOCUS_KEY) ?? "null") as FocusState | null;
    if (s && s.day === todayKey()) return s;
  } catch { /* fresh */ }
  return { mode: "focus", ends: null, left: LEN.focus, sessions: 0, day: todayKey() };
}

/** 3. A 25/5 focus timer as a ring. A finished focus block adds 25 minutes to today's focus time. Survives leaving the page. */
function FocusCard({ onLogged }: { onLogged: () => void }) {
  const [s, setS] = useState<FocusState>(loadFocus);
  const [, tick] = useState(0);
  const logged = useRef(false);
  const save = (next: FocusState) => { setS(next); try { window.localStorage.setItem(FOCUS_KEY, JSON.stringify(next)); } catch { /* fine */ } };
  const left = s.ends ? Math.max(0, Math.round((s.ends - Date.now()) / 1000)) : s.left;
  useEffect(() => {
    if (!s.ends) return;
    const t = window.setInterval(() => tick((n) => n + 1), 500);
    return () => window.clearInterval(t);
  }, [s.ends]);
  useEffect(() => {
    if (!s.ends || left > 0 || logged.current) return;
    logged.current = true;
    if (s.mode === "focus") {
      work.focus(25).then(onLogged).catch(() => {});
      try { navigator.vibrate?.(200); } catch { /* fine */ }
      save({ ...s, mode: "break", ends: null, left: LEN.break, sessions: s.sessions + 1 });
    } else {
      save({ ...s, mode: "focus", ends: null, left: LEN.focus });
    }
  }, [left, s.ends]);  // eslint-disable-line react-hooks/exhaustive-deps
  const start = () => { logged.current = false; save({ ...s, ends: Date.now() + left * 1000 }); };
  const pause = () => save({ ...s, ends: null, left });
  const reset = () => save({ ...s, ends: null, left: LEN[s.mode] });
  const mm = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  return (
    <Glass as="section" className="widget work-focus" style={{ minHeight: 0 }} aria-label="Focus timer">
      <header className="widget__head"><Timer aria-hidden="true" /><span>{s.mode === "focus" ? "Focus" : "Break"}</span><span className="widget__source">{s.sessions} done today</span></header>
      <div className="work-focus__body">
        <Ring value={1 - left / LEN[s.mode]} size={120} stroke={10} tone={s.mode === "focus" ? "accent" : "good"} label={`${s.mode}: ${mm} left`}>
          <strong className="work-ring__big" role="timer">{mm}</strong><span className="muted">{s.mode === "focus" ? "focus" : "break"}</span>
        </Ring>
        <div className="work-focus__controls">
          {s.ends ? <button type="button" className="button" onClick={pause}><Pause size={14} aria-hidden="true" /> Pause</button>
            : <button type="button" className="button button--primary" onClick={start}><Play size={14} aria-hidden="true" /> {left === LEN[s.mode] ? "Start" : "Resume"}</button>}
          <button type="button" className="chip chip--button" onClick={reset} aria-label="Reset the timer"><RotateCcw size={12} aria-hidden="true" /> Reset</button>
          <span className="work-focus__dots" aria-label={`${s.sessions} focus blocks today`}>
            {Array.from({ length: Math.max(4, s.sessions) }, (_, i) => <span key={i} className={i < s.sessions ? "on" : ""} />)}
          </span>
        </div>
      </div>
    </Glass>
  );
}

/** 5. Tiles for the work apps (links in a group named Work, or named GVW, CMP, Timesheet, SirisPM, Archive…), with whether each answers. */
function AppsCard({ w }: { w: WorkDay }) {
  const apps = w.apps ?? [];
  const status = useResource<Record<string, LinkStatus>>("links:status", () => links.status(), { staleMs: 60_000, enabled: apps.length > 0 });
  return (
    <Glass as="section" className="widget work-apps" style={{ minHeight: 0 }} aria-label="Work apps">
      <header className="widget__head"><BriefcaseBusiness aria-hidden="true" /><span>Apps and tools</span></header>
      <div className="work-app-grid">
        {apps.map((a) => {
          const st = status.data?.[a.id];
          return (
            <a key={a.id} className="work-app" href={a.url} target="_blank" rel="noreferrer" title={a.note || a.url}>
              {a.icon ? <img src={a.icon} alt="" className="work-app__icon" /> : <span className="work-app__icon work-app__letter" aria-hidden="true">{a.name.slice(0, 1)}</span>}
              <span className="work-app__name">{a.name}</span>
              {st && <span className={`work-app__state ${st.up ? "dot-good" : "dot-critical"}`} aria-label={st.up ? "Up" : "Not answering"} />}
              <ExternalLink size={11} className="work-app__out" aria-hidden="true" />
            </a>
          );
        })}
        <Link to="/engineering" className="work-app"><span className="work-app__icon work-app__glyph" aria-hidden="true"><Calculator size={20} /></span><span className="work-app__name">Calculators</span></Link>
        <Link to="/career" className="work-app"><span className="work-app__icon work-app__glyph" aria-hidden="true"><Award size={20} /></span><span className="work-app__name">Career</span></Link>
      </div>
      {!apps.length && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Put your work apps in a Links group called Work (or name them GVW, CMP, Timesheet…) and they appear here.</p>}
      {w.engineering.current && <p className="muted" style={{ margin: 0, fontSize: 13 }}>Engineering project: <strong>{w.engineering.current.name}</strong></p>}
    </Glass>
  );
}

function TodosCard({ w, onChange }: { w: WorkDay; onChange: () => void }) {
  const [gone, setGone] = useState<Set<string>>(new Set());
  const items = (w.todos ?? []).filter((t) => !gone.has(`${t.note}|${t.task}`));
  if (!w.todos?.length) return null;
  const done = async (t: { note: string; task: string }) => {
    await brain.done(t.note, t.task);
    work.todoDone().catch(() => {});
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

const CATS: { id: CpdCategory; label: string }[] = [{ id: "area", label: "Area of practice" }, { id: "risk", label: "Risk" }, { id: "business", label: "Business" }, { id: "other", label: "Other" }];

/** 4. CPD as rings: the 150 hours over three years, and Engineers Australia's three minimums, with what's short; and log an activity. */
function CpdCard({ w, onChange }: { w: WorkDay; onChange: () => void }) {
  const [c, setC] = useState(w.cpd);
  useEffect(() => setC(w.cpd), [w.cpd]);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [hours, setHours] = useState("1");
  const [cat, setCat] = useState<CpdCategory>("area");
  const [msg, setMsg] = useState<string | null>(null);
  if (!c) return null;
  const log = async () => {
    const h = Number(hours);
    if (!title.trim() || !(h > 0)) return;
    const r = await work.logCpd({ title: title.trim(), hours: h, category: cat });
    if (r.cpd) setC(r.cpd);
    setMsg(`Logged ${h} h of ${CATS.find((x) => x.id === cat)!.label.toLowerCase()}. Add it in Engineers Australia too, so it counts there.`);
    setTitle(""); setHours("1"); setOpen(false);
    onChange();
  };
  return (
    <Glass as="section" className="widget work-cpd" style={{ minHeight: 0 }} aria-label="CPD">
      <header className="widget__head"><Award aria-hidden="true" /><span>CPD</span><Link to="/career" className="widget__source">Career</Link></header>
      <div className="work-cpd__rings">
        <Ring value={c.total / Math.max(1, c.required)} size={116} stroke={11} tone={c.short ? "accent" : "good"} label={`CPD: ${c.total} of ${c.required} hours in three years`}>
          <strong className="work-ring__big">{Math.round(c.total)}</strong><span className="muted">of {c.required} h</span>
        </Ring>
        <div className="work-cpd__mins">
          {(c.minimums ?? []).map((m) => (
            <div key={m.category} className="work-cpd__min">
              <Ring value={m.hours / Math.max(1, m.minimum)} size={58} stroke={6} tone={m.short ? "warning" : "good"} label={`${m.label}: ${m.hours} of ${m.minimum} hours`}>
                <span className="work-cpd__pct">{Math.round(m.hours)}</span>
              </Ring>
              <span className="work-cpd__label">{m.label.replace(" & management", "")}<span className="muted">{m.short ? `${m.short} h short` : `${m.minimum} h met`}</span></span>
            </div>
          ))}
        </div>
      </div>
      {msg && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
      {open ? (
        <form className="stack" style={{ gap: 8 }} onSubmit={(e) => { e.preventDefault(); void log(); }}>
          <input className="field" placeholder="What (e.g. IPWEA webinar on stormwater)" aria-label="CPD activity" value={title} onChange={(e) => setTitle(e.target.value)} />
          <div className="row gym-chips" role="radiogroup" aria-label="Category">
            {CATS.map((x) => <button key={x.id} type="button" role="radio" aria-checked={cat === x.id} className={`chip chip--button ${cat === x.id ? "chip--active" : ""}`} onClick={() => setCat(x.id)}>{x.label}</button>)}
          </div>
          <div className="row" style={{ gap: 8 }}>
            <label className="row" style={{ gap: 6 }}>Hours <input className="field" style={{ width: 80 }} type="number" min={0.25} step={0.25} aria-label="Hours" value={hours} onChange={(e) => setHours(e.target.value)} /></label>
            <button type="submit" className="button button--primary" disabled={!title.trim() || !(Number(hours) > 0)}>Log it</button>
            <button type="button" className="button" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </form>
      ) : <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => { setMsg(null); setOpen(true); }}>Log CPD</button>}
    </Glass>
  );
}

const ago = (iso: string) => {
  const days = Math.round((Date.now() - new Date(`${iso}T12:00:00`).getTime()) / 86_400_000);
  return days <= 0 ? "today" : days === 1 ? "yesterday" : days < 7 ? `${days} days ago` : new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
};

/** 6. Work notes: search them, see the ones changed lately as cards, or jot one down (tagged #work, filed under Work/ tonight). */
function WorkNotesCard({ w }: { w: WorkDay }) {
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
  const folder = (p: string) => p.split("/").slice(1, -1).join(" › ") || "Work";
  return (
    <Glass as="section" className="widget work-notes" style={{ minHeight: 0 }} aria-label="Work notes">
      <header className="widget__head"><Search aria-hidden="true" /><span>Work notes</span></header>
      <label className="mini-search">
        <Search size={14} aria-hidden="true" />
        <input placeholder="Search work notes (GVW, processes, contacts…)" aria-label="Search work notes" value={q} onChange={(e) => setQ(e.target.value)} />
      </label>
      {hits ? (hits.length ? (
        <ul className="items">
          {hits.map((h) => (
            <li key={h.title} className="item"><span className="item__text"><Link className="item__title" to={`/brain?q=${encodeURIComponent(h.title)}`}>{h.title}</Link>
              {h.excerpts?.[0] && <span className="item__subtitle">{h.excerpts[0]}</span>}</span></li>
          ))}
        </ul>
      ) : <p className="muted" style={{ margin: 0 }}>No work notes match.</p>) : (w.notes?.length ? (
        <div className="work-note-cards" aria-label="Changed lately">
          {w.notes.map((n) => (
            <Link key={n.path} to={`/brain?q=${encodeURIComponent(n.title)}`} className="work-note-card">
              <span className="work-note-card__folder">{folder(n.path)}</span>
              <strong className="work-note-card__title">{n.title}</strong>
              {n.excerpt && <span className="work-note-card__text">{n.excerpt}</span>}
              {n.as_of && <span className="work-note-card__when">{ago(n.as_of)}</span>}
            </Link>
          ))}
        </div>
      ) : null)}
      <textarea className="field" rows={2} placeholder="Jot something down for work (filed under Work/ tonight)" aria-label="Work note" value={note} onChange={(e) => { setNote(e.target.value); setSaved(null); }} />
      <button type="button" className="button" style={{ alignSelf: "flex-start" }} disabled={!note.trim()} onClick={save}>Save to Siris</button>
      {saved && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{saved}</p>}
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
