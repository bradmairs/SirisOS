import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Award, CalendarCheck, Check, CheckCircle2, MoonStar, PenLine, Target } from "lucide-react";
import { useResource } from "../api/resource";
import { tasks } from "../api/tasks";
import { wrapup, type WrapMeeting, type WrapUpOverview } from "../api/wrapup";
import { Glass } from "../components/Glass";
import { TaskRow } from "./Tasks";

const clock = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "");

function Meeting({ m, onChanged }: { m: WrapMeeting; onChanged: (text: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run(fn: () => Promise<string>) {
    setBusy(true);
    setError(null);
    try {
      onChanged(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <li className="item suggest task">
      <span className="item__text">
        <div className="item__title">{m.title}</div>
        <div className="item__subtitle">
          {[`${clock(m.start)}–${clock(m.end)}`, m.location, m.cpd ? `looks like CPD · ${m.cpd.hours} h` : null].filter(Boolean).join(" · ")}
        </div>
        {error && <div className="tone-critical" style={{ fontSize: 13 }}>{error}</div>}
      </span>
      {m.cpd && (
        <span className="suggest__actions">
          <button type="button" className="chip chip--button suggest__link" disabled={busy} aria-label={`Log ${m.title} as CPD`}
            onClick={() => run(async () => { await wrapup.logCpd(m.cpd!.key, m.title, m.cpd!.hours); return `Added a task to log “${m.title}” in Engineers Australia tomorrow`; })}>
            <Award size={13} aria-hidden="true" /> Log it
          </button>
          <button type="button" className="chip chip--button" disabled={busy} aria-label={`${m.title} isn't CPD`}
            onClick={() => run(async () => { await wrapup.notCpd(m.cpd!.key); return `Won't suggest “${m.title}” as CPD`; })}>
            Not CPD
          </button>
        </span>
      )}
    </li>
  );
}

function Done({ saved }: { saved: NonNullable<WrapUpOverview["saved"]> }) {
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Wrapped up">
      <header className="widget__head"><CheckCircle2 aria-hidden="true" className="tone-good" /><span>Wrapped up</span></header>
      {saved.top3.length > 0 ? (
        <>
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>Tomorrow's top 3, waiting in the morning brief and on your task list:</p>
          <ol className="brief-top3">{saved.top3.map((t) => <li key={t}>{t}</li>)}</ol>
        </>
      ) : <p className="muted" style={{ margin: 0 }}>No top 3 for tomorrow.</p>}
      {saved.journal && <p style={{ margin: 0, fontSize: 14 }}>“{saved.journal}”{saved.journal_saved_as ? <span className="muted"> · saved to Siris</span> : <span className="tone-warning"> · couldn't reach Siris, kept here</span>}</p>}
      <Link to="/tasks" className="show-more">Open tasks</Link>
    </Glass>
  );
}

/** Two minutes at the end of the day (2.10). */
export function WrapUpScreen() {
  const res = useResource<WrapUpOverview>("wrapup:today", () => wrapup.get(), { staleMs: 15_000 });
  const data = res.data ?? null;
  const [top3, setTop3] = useState<string[] | null>(null);
  const [journal, setJournal] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    document.title = "Wrap-up · SirisOS";
  }, []);
  useEffect(() => {
    if (data && top3 === null) {
      const picked = data.saved?.top3 ?? data.suggested_top3;
      setTop3([0, 1, 2].map((i) => picked[i] ?? ""));
      setJournal(data.saved?.journal ?? "");
    }
  }, [data, top3]);

  const changed = (text: string) => {
    setNote(text);
    res.reload(true).catch(() => undefined);
  };

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await wrapup.save((top3 ?? []).map((t) => t.trim()).filter(Boolean), journal);
      setEditing(false);
      setNote(null);
      await res.reload(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save.");
    } finally {
      setBusy(false);
    }
  }

  const finished = data?.saved && !editing;
  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{data ? new Date(`${data.date}T12:00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" }) : "Today"}</p>
          <h1 className="page-head__title">Wrap up</h1>
        </div>
        {finished && <button type="button" className="button button--small" onClick={() => setEditing(true)}><PenLine size={14} aria-hidden="true" /> Change</button>}
      </header>
      <div className="stack" style={{ marginTop: 16 }}>
        {!data && !res.error && <div className="skeleton" style={{ height: 200 }} aria-label="Loading" />}
        {!data && res.error && <p className="tone-critical">{res.error}</p>}
        {note && <p className="tone-good suggest__done" role="status"><Check size={14} aria-hidden="true" /> {note}</p>}
        {finished && <Done saved={data.saved!} />}
        {data && !finished && (
          <>
            <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Today">
              <header className="widget__head"><CheckCircle2 aria-hidden="true" /><span>1 · Today</span></header>
              {data.done.length > 0 && <p className="tone-good" style={{ margin: 0, fontSize: 14 }}>Done today: {data.done.map((d) => d.title).join(", ")}.</p>}
              {data.open.length === 0 ? (
                <p className="muted" style={{ margin: 0 }}>{data.done.length ? "Nothing else left from today." : "Nothing was due today."}</p>
              ) : (
                <>
                  <p className="muted" style={{ margin: 0, fontSize: 14 }}>Still open: tick what you did, snooze the rest.</p>
                  <ul className="items">{data.open.map((t) => <TaskRow key={t.id} task={t} compact onChanged={changed} />)}</ul>
                  <button type="button" className="chip chip--button" style={{ alignSelf: "flex-start" }} disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await Promise.all(data.open.map((t) => tasks.snooze(t.id, "tomorrow")));
                        changed(`Moved ${data.open.length} to tomorrow`);
                      } finally {
                        setBusy(false);
                      }
                    }}>
                    Move the rest to tomorrow
                  </button>
                </>
              )}
            </Glass>

            <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Meetings">
              <header className="widget__head"><CalendarCheck aria-hidden="true" /><span>2 · Today's meetings</span></header>
              {data.calendar_unavailable ? <p className="muted" style={{ margin: 0 }}>The calendar didn't answer.</p>
                : data.meetings.length === 0 ? <p className="muted" style={{ margin: 0 }}>No meetings today.</p>
                : <ul className="items">{data.meetings.map((m) => <Meeting key={`${m.title}-${m.start}`} m={m} onChanged={changed} />)}</ul>}
            </Glass>

            <Glass as="form" className="widget" style={{ minHeight: 0 }} onSubmit={save} aria-label="Tomorrow">
              <header className="widget__head"><Target aria-hidden="true" /><span>3 · Tomorrow's top 3</span></header>
              {(top3 ?? ["", "", ""]).map((value, i) => (
                <input key={i} className="field" value={value} placeholder={["The one thing that matters most", "Then this", "And this"][i]}
                  aria-label={`Top ${i + 1}`} onChange={(e) => setTop3((all) => (all ?? ["", "", ""]).map((v, j) => (j === i ? e.target.value : v)))} />
              ))}
              <header className="widget__head" style={{ marginTop: 6 }}><MoonStar aria-hidden="true" /><span>4 · One line about today</span></header>
              <textarea className="field" rows={2} placeholder="How did it go? Each sentence is filed in Siris, on the note it's about." value={journal} onChange={(e) => setJournal(e.target.value)} aria-label="One line about today" />
              <button type="submit" className="button button--primary" disabled={busy}>{busy ? "Saving…" : "Done for today"}</button>
              {error && <p className="tone-critical" role="alert" style={{ margin: 0 }}>{error}</p>}
            </Glass>
          </>
        )}
      </div>
    </>
  );
}
