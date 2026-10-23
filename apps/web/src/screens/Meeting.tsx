import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BrainCircuit, CalendarClock, Check, ListTodo, Mail, NotebookPen, Users } from "lucide-react";
import { meetings, prepLink, type MeetingPrep } from "../api/meetings";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";
import { TaskRow } from "./Tasks";

const when = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "");
const day = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" }) : "");

function Picker() {
  const res = useResource("meetings:upcoming", () => meetings.list(), { staleMs: 60_000 });
  const list = res.data?.meetings ?? null;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0, marginTop: 16 }} aria-label="Meetings">
      <header className="widget__head"><CalendarClock aria-hidden="true" /><span>Today and tomorrow</span></header>
      {!list && !res.error && <div className="skeleton" style={{ height: 60 }} />}
      {res.error && !list && <p className="tone-critical" style={{ margin: 0 }}>{res.error}</p>}
      {list?.length === 0 && <p className="muted" style={{ margin: 0 }}>No meetings coming up.</p>}
      <ul className="items">
        {list?.map((m) => (
          <li key={`${m.title}-${m.start}`} className="item">
            <span className="item__text">
              <Link to={prepLink(m.title, m.start)} className="item__title" style={{ color: "inherit" }}>{m.title}</Link>
              <div className="item__subtitle">{[`${day(m.start)} ${when(m.start)}`, m.location, m.attendees.length ? `${m.attendees.length} people` : null].filter(Boolean).join(" · ")}</div>
            </span>
          </li>
        ))}
      </ul>
    </Glass>
  );
}

function Notes({ prep }: { prep: MeetingPrep }) {
  const key = `sirisos.meeting-notes:${prep.title}:${prep.start ?? ""}`;
  const [text, setText] = useState(() => { try { return localStorage.getItem(key) ?? ""; } catch { return ""; } });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { try { localStorage.setItem(key, text); } catch { /* fine */ } }, [key, text]);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const r = await meetings.saveNotes(prep.title, prep.start, text);
      setDone(`Saved to Siris as “${r.saved_as}”${r.tasks.length ? `, and added ${r.tasks.length} task${r.tasks.length === 1 ? "" : "s"}: ${r.tasks.join(", ")}` : ""}.`);
      setText("");
      try { localStorage.removeItem(key); } catch { /* fine */ }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Notes">
      <header className="widget__head"><NotebookPen aria-hidden="true" /><span>Notes</span></header>
      <textarea className="field" rows={6} value={text} onChange={(e) => setText(e.target.value)} aria-label="Meeting notes"
        placeholder={"What was decided?\n- [ ] Actions on their own line become tasks"} />
      <button type="button" className="button button--small button--primary" disabled={busy || !text.trim()} onClick={save}>{busy ? "Saving…" : "Save to Siris"}</button>
      {done && <p className="tone-good suggest__done" role="status" style={{ margin: 0 }}><Check size={14} aria-hidden="true" /> {done}</p>}
      {error && <p className="tone-critical" role="alert" style={{ margin: 0 }}>{error}</p>}
    </Glass>
  );
}

/** Before a meeting: what Siris knows and the latest emails; after it, notes into Siris (3.2). */
export function MeetingScreen() {
  const [params] = useSearchParams();
  const title = params.get("title");
  const start = params.get("start");
  const res = useResource<MeetingPrep | null>(`meetings:prep:${title}:${start}`, () => (title ? meetings.prep(title, start) : Promise.resolve(null)), { staleMs: 60_000 });
  const prep = res.data ?? null;
  const [taskNote, setTaskNote] = useState<string | null>(null);

  useEffect(() => {
    document.title = `${title ?? "Meetings"} · SirisOS`;
  }, [title]);

  if (!title) {
    return (
      <>
        <header className="page-head"><div><p className="page-head__eyebrow">Prepare</p><h1 className="page-head__title">Meetings</h1></div></header>
        <Picker />
      </>
    );
  }
  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{prep?.start ? `${day(prep.start)} · ${when(prep.start)}${prep.end ? `–${when(prep.end)}` : ""}` : "Meeting"}</p>
          <h1 className="page-head__title">{title}</h1>
        </div>
      </header>
      {prep?.location && <p className="muted" style={{ marginTop: 4 }}>{prep.location}</p>}
      <div className="stack" style={{ marginTop: 14 }}>
        {!prep && !res.error && <div className="skeleton" style={{ height: 160 }} aria-label="Loading" />}
        {!prep && res.error && <p className="tone-critical">{res.error}</p>}
        {prep && (
          <>
            {prep.people.length > 0 && (
              <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="People">
                <header className="widget__head"><Users aria-hidden="true" /><span>People</span></header>
                <div className="insights__topics">{prep.people.map((p) => <span key={p.email} className="chip" title={p.email}>{p.name}</span>)}</div>
              </Glass>
            )}
            <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="In Siris">
              <header className="widget__head"><BrainCircuit aria-hidden="true" /><span>In Siris</span></header>
              {prep.notes.length === 0 ? <p className="muted" style={{ margin: 0 }}>Nothing in Siris about this yet.</p> : (
                <ul className="items">
                  {prep.notes.map((n) => (
                    <li key={n.title} className="item task">
                      <span className="item__text">
                        <Link to={`/brain?q=${encodeURIComponent(n.title)}`} className="item__title" style={{ color: "inherit" }}>{n.title}</Link>
                        {n.excerpt && <div className="item__subtitle" style={{ whiteSpace: "normal" }}>{n.excerpt}</div>}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Glass>
            {prep.emails !== null && (
              <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Recent emails">
                <header className="widget__head"><Mail aria-hidden="true" /><span>Latest emails from them</span></header>
                {prep.emails.length === 0 ? <p className="muted" style={{ margin: 0 }}>No emails from them in the last two months.</p> : (
                  <ul className="items">
                    {prep.emails.map((m) => (
                      <li key={m.uid} className="item task">
                        <span className="item__text">
                          <div className="item__title">{m.subject}</div>
                          <div className="item__subtitle" style={{ whiteSpace: "normal" }}>{m.sender}{m.date ? ` · ${new Date(m.date).toLocaleDateString(undefined, { day: "numeric", month: "short" })}` : ""}{m.snippet ? ` · ${m.snippet}` : ""}</div>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Glass>
            )}
            {prep.tasks.length > 0 && (
              <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Related tasks">
                <header className="widget__head"><ListTodo aria-hidden="true" /><span>Related tasks</span></header>
                <ul className="items">{prep.tasks.map((t) => <TaskRow key={t.id} task={t} compact onChanged={(m) => { setTaskNote(m); res.reload(true).catch(() => undefined); }} />)}</ul>
                {taskNote && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{taskNote}</p>}
              </Glass>
            )}
            <Notes prep={prep} />
          </>
        )}
      </div>
    </>
  );
}
