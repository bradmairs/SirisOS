import { useEffect, useRef, useState } from "react";
import { BookHeart, Brain, ChevronDown, Flower2, LifeBuoy, Lightbulb, Shield, Smile, Trash2, Wind } from "lucide-react";
import { health } from "../api/health";
import { mind, type Clarity, type JournalEntry, type Mind, type MindDay } from "../api/mind";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

/** Health's Mental health tab (9.1): mood and mindful minutes from Apple Health, what goes with a better mood, calming
 * tools, a journal, and Clarity, a private streak that stays closed until you open it. */
export function MindView() {
  const res = useResource<Mind>("mind", () => mind.get(), { staleMs: 60_000, persist: true });
  const m = res.data;
  const reload = () => res.reload?.(true);
  return (
    <>
      {!m && res.error && <div className="error-banner" role="alert">{res.error}</div>}
      {!m && !res.error && <div className="skeleton" style={{ height: 220 }} aria-busy="true" />}
      {m && <MoodCard m={m} onChange={reload} />}
      {m && <MindfulCard m={m} />}
      {m && m.patterns.length > 0 && <PatternsCard m={m} />}
      <ToolsCard onDone={reload} />
      {m && <JournalCard entries={m.journal} onChange={reload} />}
      <ClarityCard />
      <SupportCard />
    </>
  );
}

const shortDay = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
const signed = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(2)}`;

/** Each day's mood as a bar up (pleasant) or down (unpleasant) from neutral. */
function MoodChart({ days }: { days: MindDay[] }) {
  const W = 300, H = 90, mid = H / 2, bw = W / Math.max(days.length, 1);
  return (
    <svg className="mind-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Mood over the last ${days.length} days`} preserveAspectRatio="none">
      <line x1={0} x2={W} y1={mid} y2={mid} className="mind-chart__axis" />
      {days.map((d, i) => d.valence == null ? null : (
        <rect key={d.date} x={i * bw + bw * 0.2} width={Math.max(1.5, bw * 0.45)} rx={1.5}
          y={d.valence >= 0 ? mid - Math.max(1.5, d.valence * (mid - 4)) : mid} height={Math.max(1.5, Math.abs(d.valence) * (mid - 4))}
          className={d.valence >= 0 ? "mind-chart__up" : "mind-chart__down"}>
          <title>{`${shortDay(d.date)}: ${d.word ?? ""} (${signed(d.valence)})`}</title>
        </rect>
      ))}
    </svg>
  );
}

function MinutesChart({ days }: { days: MindDay[] }) {
  const W = 300, H = 60, bw = W / Math.max(days.length, 1);
  const total = (d: MindDay) => (d.mindful_minutes ?? 0) + (d.here_minutes ?? 0);
  const top = Math.max(10, ...days.map(total));
  return (
    <svg className="mind-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Mindful minutes over the last ${days.length} days`} preserveAspectRatio="none">
      <line x1={0} x2={W} y1={H - 0.5} y2={H - 0.5} className="mind-chart__axis" />
      {days.map((d, i) => total(d) > 0 && (
        <rect key={d.date} x={i * bw + bw * 0.2} width={Math.max(1.5, bw * 0.45)} rx={1.5} y={H - (total(d) / top) * (H - 4)} height={(total(d) / top) * (H - 4)} className="mind-chart__up">
          <title>{`${shortDay(d.date)}: ${Math.round(total(d))} min`}</title>
        </rect>
      ))}
    </svg>
  );
}

function MoodCard({ m, onChange }: { m: Mind; onChange: () => void }) {
  const [note, setNote] = useState<string | null>(null);
  const log = async (n: number) => {
    try { const r = await health.log("mood", n); setNote(r.queued ? "Saved on this phone; it goes when SirisOS is back." : `Mood ${n} logged.`); onChange(); }
    catch (e) { setNote(e instanceof Error ? e.message : "Couldn't log it."); }
  };
  const t = m.today, w = m.week;
  const change = w.valence != null && w.before != null ? w.valence - w.before : null;
  const hasMood = m.days.some((d) => d.valence != null);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Mood">
      <header className="widget__head"><Smile aria-hidden="true" /><span>Mood</span></header>
      <div className="metrics metrics--compact">
        <div><div className="metric__value mind-word">{t?.word ?? "–"}</div><div className="metric__label">Today</div></div>
        <div><div className="metric__value mind-word">{w.word ?? "–"}</div><div className="metric__label">This week ({w.mood_days} days)</div></div>
        <div><div className="metric__value mind-word">{change == null ? "–" : Math.abs(change) < 0.05 ? "Steady" : change > 0 ? "Up" : "Down"}</div><div className="metric__label">On last week</div></div>
      </div>
      {hasMood ? <MoodChart days={m.days} /> : (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>{m.available
          ? "No mood yet. Log one below, or in Apple Health (State of Mind); for those to arrive, add State of Mind to a Health Auto Export automation sending to SirisAI."
          : "SirisAI isn't answering, so Apple Health's mood can't be shown. The tools below still work."}</p>
      )}
      <div className="row" style={{ gap: 6, flexWrap: "wrap" }} role="group" aria-label="How are you feeling?">
        <span className="muted" style={{ fontSize: 13 }}>Right now:</span>
        {[["1", "Awful"], ["2", "Low"], ["3", "OK"], ["4", "Good"], ["5", "Great"]].map(([n, label]) => (
          <button key={n} type="button" className="chip chip--button" aria-label={`Mood ${n} of 5: ${label}`} onClick={() => log(Number(n))}>{label}</button>
        ))}
      </div>
      {note && <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>{note}</p>}
    </Glass>
  );
}

function MindfulCard({ m }: { m: Mind }) {
  const w = m.week;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Mindful minutes">
      <header className="widget__head"><Flower2 aria-hidden="true" /><span>Mindful minutes</span></header>
      <div className="metrics metrics--compact">
        <div><div className="metric__value">{Math.round((m.today?.mindful_minutes ?? 0) + (m.today?.here_minutes ?? 0))}</div><div className="metric__label">Today</div></div>
        <div><div className="metric__value">{Math.round(w.mindful_minutes)}</div><div className="metric__label">This week</div></div>
        <div><div className="metric__value">{Math.round(w.mindful_before)}</div><div className="metric__label">Last week</div></div>
      </div>
      <MinutesChart days={m.days} />
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>From Apple Health (the Mindfulness app, or any app that writes mindful minutes), plus time on the tools below ({m.tools_minutes_week} min this week).</p>
    </Glass>
  );
}

function PatternsCard({ m }: { m: Mind }) {
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="What helps your mood">
      <header className="widget__head"><Lightbulb aria-hidden="true" /><span>What helps</span></header>
      <ul className="items">
        {m.patterns.map((p) => (
          <li key={p.key} className="item"><span className="item__text"><span className="item__title career-wrap">{p.text}</span>
            <span className="item__subtitle">{signed(p.with)} against {signed(p.without)}, over {p.days} days</span></span></li>
        ))}
      </ul>
    </Glass>
  );
}

/* -- tools ------------------------------------------------------------------------------------------------------- */

const PATTERNS = {
  box: { name: "Box breathing", steps: [["In", 4], ["Hold", 4], ["Out", 4], ["Hold", 4]] },
  relax: { name: "4-7-8", steps: [["In", 4], ["Hold", 7], ["Out", 8]] },
  sigh: { name: "Long sigh", steps: [["In", 2], ["In again", 1], ["Out slowly", 6]] },
} as const;
type Pattern = keyof typeof PATTERNS;

function ToolsCard({ onDone }: { onDone: () => void }) {
  const [tool, setTool] = useState<"breathe" | "ground" | "reframe" | "gratitude">("breathe");
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Tools">
      <header className="widget__head"><Brain aria-hidden="true" /><span>Tools</span></header>
      <div className="row career-views" role="tablist" aria-label="Tools">
        {([["breathe", "Breathe"], ["ground", "Ground"], ["reframe", "Reframe"], ["gratitude", "Three good things"]] as const).map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tool === id} className={`chip chip--button ${tool === id ? "chip--active" : ""}`} onClick={() => setTool(id)}>{label}</button>
        ))}
      </div>
      {tool === "breathe" && <Breathe onDone={onDone} />}
      {tool === "ground" && <Ground onDone={onDone} />}
      {tool === "reframe" && <Reframe onDone={onDone} />}
      {tool === "gratitude" && <Gratitude onDone={onDone} />}
    </Glass>
  );
}

/** Paced breathing: the circle grows as you breathe in and shrinks as you breathe out. The time counts as mindful minutes here. */
export function Breathe({ onDone, minutes: start = 2, tool = "breathing" }: { onDone?: () => void; minutes?: number; tool?: "breathing" | "urge" }) {
  const [pattern, setPattern] = useState<Pattern>("box");
  const [minutes, setMinutes] = useState(start);
  const [run, setRun] = useState<{ began: number } | null>(null);
  const [, tick] = useState(0);
  const saved = useRef(false);
  useEffect(() => { if (!run) return; const t = window.setInterval(() => tick((n) => n + 1), 250); return () => window.clearInterval(t); }, [run]);
  const steps = PATTERNS[pattern].steps;
  const cycle = steps.reduce((n, [, s]) => n + s, 0);
  const elapsed = run ? (Date.now() - run.began) / 1000 : 0;
  const left = Math.max(0, minutes * 60 - elapsed);
  let at = elapsed % cycle, step = 0;
  while (run && at >= steps[step][1]) { at -= steps[step][1]; step = (step + 1) % steps.length; }
  const [label, secs] = steps[step];
  const phase = label.startsWith("In") ? at / secs : label.startsWith("Out") ? 1 - at / secs : (steps[(step + steps.length - 1) % steps.length][0].startsWith("In") ? 1 : 0);
  const finish = (done: boolean) => {
    const seconds = Math.round(Math.min(elapsed, minutes * 60));
    setRun(null);
    if (!saved.current && seconds >= 10) { saved.current = true; mind.session(tool, seconds).then(() => onDone?.()).catch(() => {}); }
    if (done) try { navigator.vibrate?.(200); } catch { /* no */ }
  };
  useEffect(() => { if (run && left <= 0) finish(true); });
  return (
    <div className="stack" style={{ gap: 10, alignItems: "center" }}>
      {!run && (
        <div className="row" style={{ gap: 6, flexWrap: "wrap", justifyContent: "center" }}>
          {(Object.keys(PATTERNS) as Pattern[]).map((p) => <button key={p} type="button" className={`chip chip--button ${pattern === p ? "chip--active" : ""}`} aria-pressed={pattern === p} onClick={() => setPattern(p)}>{PATTERNS[p].name}</button>)}
          <select className="input" aria-label="How long" value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}>
            {[1, 2, 3, 5, 10].map((n) => <option key={n} value={n}>{n} min</option>)}
          </select>
        </div>
      )}
      <div className="mind-breath" aria-hidden="true"><span style={{ transform: `scale(${0.45 + 0.55 * (run ? phase : 0.3)})` }} /></div>
      <p role="status" style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>{run ? `${label} · ${Math.ceil(secs - at)}` : PATTERNS[pattern].name}</p>
      {run && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{Math.floor(left / 60)}:{String(Math.floor(left % 60)).padStart(2, "0")} left</p>}
      {run ? <button type="button" className="button" onClick={() => finish(false)}>Stop</button>
        : <button type="button" className="button button--primary" onClick={() => { saved.current = false; setRun({ began: Date.now() }); }}>Start</button>}
    </div>
  );
}

const SENSES = [["5", "things you can see"], ["4", "things you can touch"], ["3", "things you can hear"], ["2", "things you can smell"], ["1", "thing you can taste"]] as const;

/** 5-4-3-2-1 grounding: one sense at a time, back to the room you're in. */
function Ground({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(-1);
  const began = useRef(0);
  if (step < 0) return (
    <div className="stack" style={{ gap: 8 }}>
      <p style={{ margin: 0 }}>When your head's racing: name what's around you, one sense at a time.</p>
      <button type="button" className="button button--primary" style={{ alignSelf: "flex-start" }} onClick={() => { began.current = Date.now(); setStep(0); }}>Start</button>
    </div>
  );
  if (step >= SENSES.length) return (
    <div className="stack" style={{ gap: 8 }}>
      <p style={{ margin: 0 }}>Done. Take one slow breath out.</p>
      <button type="button" className="button" style={{ alignSelf: "flex-start" }} onClick={() => setStep(-1)}>Again</button>
    </div>
  );
  const [n, what] = SENSES[step];
  return (
    <div className="stack" style={{ gap: 8 }}>
      <p role="status" style={{ margin: 0, fontSize: 18 }}><strong>{n}</strong> {what}</p>
      <button type="button" className="button button--primary" style={{ alignSelf: "flex-start" }} onClick={() => {
        if (step === SENSES.length - 1) mind.session("grounding", Math.max(10, Math.round((Date.now() - began.current) / 1000))).then(onDone).catch(() => {});
        setStep(step + 1);
      }}>{step === SENSES.length - 1 ? "Done" : "Next"}</button>
    </div>
  );
}

/** A thought, looked at again: what happened, what you told yourself, the evidence, and a fairer way to see it. */
function Reframe({ onDone }: { onDone: () => void }) {
  const [f, setF] = useState({ situation: "", thought: "", evidence: "", balanced: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const fields: [keyof typeof f, string, string][] = [
    ["situation", "What happened?", "The meeting ran over and I missed the gym"],
    ["thought", "What did you tell yourself?", "I always let things slip"],
    ["evidence", "What's the evidence for and against it?", "I've trained 3 times this week"],
    ["balanced", "A fairer way to see it", "One missed session doesn't undo the week"],
  ];
  return (
    <form className="stack" style={{ gap: 8 }} onSubmit={async (e) => {
      e.preventDefault();
      if (!f.thought.trim() || !f.balanced.trim()) { setMsg("Fill in the thought and a fairer way to see it."); return; }
      try { await mind.journal("reframe", f.balanced.trim(), { situation: f.situation, thought: f.thought, evidence: f.evidence }); setF({ situation: "", thought: "", evidence: "", balanced: "" }); setMsg("Saved to your journal."); onDone(); }
      catch (err) { setMsg(err instanceof Error ? err.message : "Couldn't save it."); }
    }}>
      {fields.map(([k, label, ph]) => (
        <label key={k} className="stack" style={{ gap: 4, fontSize: 13 }}>{label}
          <textarea className="field" rows={2} placeholder={ph} value={f[k]} maxLength={500} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></label>
      ))}
      <button type="submit" className="button button--primary" style={{ alignSelf: "flex-start" }}>Save</button>
      {msg && <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
    </form>
  );
}

function Gratitude({ onDone }: { onDone: () => void }) {
  const [items, setItems] = useState(["", "", ""]);
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <form className="stack" style={{ gap: 8 }} onSubmit={async (e) => {
      e.preventDefault();
      const said = items.map((x) => x.trim()).filter(Boolean);
      if (!said.length) return;
      try { await mind.journal("gratitude", said.join("\n")); setItems(["", "", ""]); setMsg("Saved."); onDone(); }
      catch (err) { setMsg(err instanceof Error ? err.message : "Couldn't save it."); }
    }}>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Three things that went well today, however small, and why.</p>
      {items.map((v, i) => <input key={i} className="field" aria-label={`Good thing ${i + 1}`} value={v} maxLength={300} onChange={(e) => setItems(items.map((x, j) => (j === i ? e.target.value : x)))} />)}
      <button type="submit" className="button button--primary" style={{ alignSelf: "flex-start" }}>Save</button>
      {msg && <p className="muted" role="status" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
    </form>
  );
}

function JournalCard({ entries, onChange }: { entries: JournalEntry[]; onChange: () => void }) {
  const [text, setText] = useState("");
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Journal">
      <header className="widget__head"><BookHeart aria-hidden="true" /><span>Journal</span></header>
      <form className="row" style={{ gap: 8 }} onSubmit={async (e) => { e.preventDefault(); if (!text.trim()) return; await mind.journal("note", text.trim()); setText(""); onChange(); }}>
        <input className="field" style={{ flex: 1, minWidth: 0 }} placeholder="What's on your mind?" aria-label="Journal entry" value={text} maxLength={2000} onChange={(e) => setText(e.target.value)} />
        <button type="submit" className="button">Add</button>
      </form>
      {entries.length > 0 && (
        <ul className="items">
          {entries.map((j) => (
            <li key={j.id} className="item">
              <span className="item__text">
                <span className="item__title career-wrap">{j.kind === "reframe" && j.thought ? `“${j.thought}” → ${j.text}` : j.text.split("\n").join(" · ")}</span>
                <span className="item__subtitle">{shortDay(j.at.slice(0, 10))} · {j.kind === "gratitude" ? "good things" : j.kind === "reframe" ? "reframe" : "note"}</span>
              </span>
              <button type="button" className="icon-link" aria-label="Delete the entry" onClick={async () => { if (window.confirm("Delete this entry?")) { await mind.unjournal(j.id); onChange(); } }}><Trash2 size={14} aria-hidden="true" /></button>
            </li>
          ))}
        </ul>
      )}
    </Glass>
  );
}

/* -- Clarity ----------------------------------------------------------------------------------------------------- */

const TRIGGERS = ["Bored", "Stressed", "Tired", "Lonely", "Late night", "Phone in bed", "After a drink", "Other"];
const ALTERNATIVES = ["Leave the room you're in", "Phone in another room for 20 minutes", "Cold water on your face", "20 push-ups or a short walk", "Message someone", "Two minutes' breathing (below)"];

/** Clarity: a private streak. Closed each time you come to the page, and only fetched once you open it. */
function ClarityCard() {
  const [open, setOpen] = useState(false);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Clarity">
      <button type="button" className="widget__head mind-fold" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Shield aria-hidden="true" /><span>Clarity</span><ChevronDown size={16} aria-hidden="true" className={open ? "mind-fold__open" : ""} />
      </button>
      {open && <ClarityBody />}
    </Glass>
  );
}

function ClarityBody() {
  const res = useResource<Clarity>("mind:clarity", () => mind.clarity(), { staleMs: 30_000 });
  const c = res.data;
  const [urge, setUrge] = useState<{ began: number; trigger: string } | null>(null);
  const [editing, setEditing] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const set = (next: Clarity) => res.mutate?.(next);
  if (!c) return res.error ? <p className="tone-warning" style={{ margin: 0 }}>{res.error}</p> : <div className="skeleton" style={{ height: 120 }} aria-busy="true" />;
  if (!c.started) return (
    <div className="stack" style={{ gap: 8 }}>
      <p style={{ margin: 0 }}>A private streak: days clear, the urges you ride out, and what sets them off. It stays on SirisOS only.</p>
      <button type="button" className="button button--primary" style={{ alignSelf: "flex-start" }} onClick={async () => set(await mind.start())}>Start today</button>
    </div>
  );
  if (urge) return <UrgeMode c={c} trigger={urge.trigger} began={urge.began} onEnd={(next, text) => { set(next); setUrge(null); setMsg(text); }} />;
  return (
    <div className="stack" style={{ gap: 10 }}>
      <div className="metrics metrics--compact">
        <div><div className="metric__value">{c.streak}</div><div className="metric__label">Days clear</div></div>
        <div><div className="metric__value">{c.best}</div><div className="metric__label">Best</div></div>
        <div><div className="metric__value">{c.clear_last_30}/30</div><div className="metric__label">Last 30 days</div></div>
      </div>
      {c.next && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{c.next.left} day{c.next.left === 1 ? "" : "s"} to {c.next.days}.</p>}
      <div className="mind-month" role="img" aria-label={`Last 30 days: ${c.clear_last_30} clear`}>
        {c.month.map((d) => <span key={d.date} className={`mind-month__day ${d.status ? `mind-month__day--${d.status}` : ""}`} title={`${shortDay(d.date)}${d.status ? `: ${d.status}` : ""}`} />)}
      </div>
      <button type="button" className="button button--primary" onClick={() => setUrge({ began: Date.now(), trigger: "" })}>I'm having an urge</button>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <span className="muted" style={{ fontSize: 13 }}>Today:</span>
        <button type="button" className={`chip chip--button ${c.checked_today === "clear" ? "chip--active" : ""}`} onClick={async () => { set(await mind.check("clear")); setMsg("Another clear day."); }}>Clear</button>
        <button type="button" className={`chip chip--button ${c.checked_today === "slip" ? "chip--active" : ""}`} onClick={async () => {
          if (!window.confirm("Log a slip? The streak starts again from today; your best and your history stay.")) return;
          set(await mind.check("slip")); setMsg(`A slip isn't starting over: ${c.clear_last_30} of your last 30 days were clear. Look at what set it off, and go again.`);
        }}>Slipped</button>
      </div>
      {msg && <p role="status" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
      {(c.urges_week > 0 || c.rode_out_all > 0) && (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>This week: {c.urges_week} urge{c.urges_week === 1 ? "" : "s"}, {c.rode_out_week} ridden out. {c.rode_out_all} ridden out in all.</p>
      )}
      {c.triggers.length > 0 && (
        <div className="stack" style={{ gap: 4 }}>
          <span className="muted" style={{ fontSize: 13 }}>What sets it off (60 days)</span>
          <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>{c.triggers.map((t) => <span key={t.trigger} className="chip">{t.trigger} · {t.count}</span>)}</div>
          <span className="muted" style={{ fontSize: 13 }}>When: {c.times.filter((t) => t.count).map((t) => `${t.part} ${t.count}`).join(", ") || "–"}</span>
        </div>
      )}
      {editing ? <PlanEditor c={c} onSaved={(next) => { set(next); setEditing(false); }} /> : (
        <div className="stack" style={{ gap: 4 }}>
          <span className="muted" style={{ fontSize: 13 }}>Why it matters to you</span>
          {c.reasons.length ? <ul className="mind-list">{c.reasons.map((r) => <li key={r}>{r}</li>)}</ul> : <p className="muted" style={{ margin: 0, fontSize: 13 }}>Add your reasons: they're shown when an urge hits.</p>}
          <span className="muted" style={{ fontSize: 13 }}>Your plan</span>
          {c.plan.length ? <ul className="mind-list">{c.plan.map((r) => <li key={r}>{r}</li>)}</ul> : <p className="muted" style={{ margin: 0, fontSize: 13 }}>e.g. phone charges outside the bedroom; Screen Time's web content limit on (Settings, Screen Time, Content & Privacy Restrictions).</p>}
          <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} onClick={() => setEditing(true)}>Edit reasons and plan</button>
        </div>
      )}
    </div>
  );
}

/** An urge, ridden out: your reasons, something else to do, and a timer. Urges peak and pass, usually within 15 minutes. */
function UrgeMode({ c, trigger: first, began, onEnd }: { c: Clarity; trigger: string; began: number; onEnd: (c: Clarity, msg: string) => void }) {
  const [trigger, setTrigger] = useState(first);
  const [, tick] = useState(0);
  useEffect(() => { const t = window.setInterval(() => tick((n) => n + 1), 1000); return () => window.clearInterval(t); }, []);
  const gone = Math.floor((Date.now() - began) / 1000);
  const end = async (outcome: "rode" | "slip") => {
    if (gone >= 10) mind.session("urge", gone).catch(() => {});
    const next = await mind.urge(trigger, outcome);
    onEnd(next, outcome === "rode" ? `Ridden out. That's ${next.rode_out_all}.` : "Logged. The streak starts again from today; your best stays.");
  };
  return (
    <div className="stack" style={{ gap: 10 }}>
      <p style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>It'll pass. Most urges peak and fade within 15 minutes.</p>
      <p className="muted" role="timer" style={{ margin: 0 }}>{Math.floor(gone / 60)}:{String(gone % 60).padStart(2, "0")} so far · {c.streak} days clear</p>
      {c.reasons.length > 0 && <ul className="mind-list">{c.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
      <span className="muted" style={{ fontSize: 13 }}>Do one of these now</span>
      <ul className="mind-list">{(c.plan.length ? c.plan : ALTERNATIVES).map((a) => <li key={a}>{a}</li>)}</ul>
      <details><summary className="muted" style={{ fontSize: 13 }}>Breathe with it</summary><Breathe minutes={2} tool="urge" /></details>
      <div className="row" style={{ gap: 6, flexWrap: "wrap" }} role="group" aria-label="What set it off?">
        {TRIGGERS.map((t) => <button key={t} type="button" aria-pressed={trigger === t.toLowerCase()} className={`chip chip--button ${trigger === t.toLowerCase() ? "chip--active" : ""}`} onClick={() => setTrigger(t.toLowerCase())}>{t}</button>)}
      </div>
      <div className="row" style={{ gap: 8 }}>
        <button type="button" className="button button--primary" onClick={() => end("rode")}>It passed</button>
        <button type="button" className="button" onClick={() => end("slip")}>I slipped</button>
      </div>
    </div>
  );
}

function PlanEditor({ c, onSaved }: { c: Clarity; onSaved: (c: Clarity) => void }) {
  const [reasons, setReasons] = useState(c.reasons.join("\n"));
  const [plan, setPlan] = useState(c.plan.join("\n"));
  const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
  return (
    <form className="stack" style={{ gap: 8 }} onSubmit={async (e) => { e.preventDefault(); onSaved(await mind.plan(lines(reasons), lines(plan))); }}>
      <label className="stack" style={{ gap: 4, fontSize: 13 }}>Why it matters to you (one a line)
        <textarea className="field" rows={3} value={reasons} onChange={(e) => setReasons(e.target.value)} /></label>
      <label className="stack" style={{ gap: 4, fontSize: 13 }}>Your plan: what you'll do instead, and what makes it harder (one a line)
        <textarea className="field" rows={3} value={plan} onChange={(e) => setPlan(e.target.value)} /></label>
      <button type="submit" className="button button--primary" style={{ alignSelf: "flex-start" }}>Save</button>
    </form>
  );
}

function SupportCard() {
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Support">
      <header className="widget__head"><LifeBuoy aria-hidden="true" /><span>If it's too much</span></header>
      <p style={{ margin: 0, fontSize: 14 }}>Talk to someone, any time: <a className="brief-link" href="tel:131114">Lifeline 13 11 14</a> · <a className="brief-link" href="tel:1300224636">Beyond Blue 1300 22 4636</a>. In an emergency, call <a className="brief-link" href="tel:000">000</a>. A GP can set up a Mental Health Treatment Plan for subsidised sessions with a psychologist.</p>
      <p className="muted" style={{ margin: 0, fontSize: 12 }}><Wind size={12} aria-hidden="true" /> These tools help day to day; they aren't a replacement for care.</p>
    </Glass>
  );
}
