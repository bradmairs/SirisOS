import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { CalendarDays, CheckCircle2, Circle, FolderKanban, Link2, Mail, Plus } from "lucide-react";
import { useResource } from "../api/resource";
import { dueWords, FINISHED, projects, type ProjectPage, type ProjectSummary } from "../api/projects";
import { dueLabel, tasks, type TaskItem } from "../api/tasks";
import { Glass } from "../components/Glass";
import { useShowMore } from "../components/ShowMore";

/** Every Siris project: what's due, what's gone quiet, open tasks (4.0). */
export function ProjectsScreen() {
  const { data, error, loading } = useResource("siris-projects", () => projects.list(), { staleMs: 60_000, persist: true });
  useEffect(() => {
    document.title = "Projects · SirisOS";
  }, []);
  const active = (data?.projects ?? []).filter((p) => !FINISHED.includes(p.status));
  const finished = (data?.projects ?? []).filter((p) => FINISHED.includes(p.status));
  const done = useShowMore(finished);
  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{data ? `${active.length} active` : "Siris"}</p>
          <h1 className="page-head__title">Projects</h1>
        </div>
      </header>
      {error && !data && <div className="error-banner" role="alert">{error}</div>}
      {!data && loading && <div className="skeleton" style={{ height: 200, marginTop: 16 }} />}
      {data && !data.available && <p className="muted" style={{ margin: "16px 6px" }}>Siris isn't reachable right now (SirisAI 2.25 or later lists projects).</p>}
      {data?.available && data.projects.length === 0 && <p className="muted" style={{ margin: "16px 6px" }}>No project notes in Siris yet.</p>}
      {active.length > 0 && (
        <Glass as="section" className="widget" style={{ minHeight: 0, marginTop: 16 }} aria-label="Active projects">
          <ul className="items">{active.map((p) => <ProjectRow key={p.title} project={p} />)}</ul>
        </Glass>
      )}
      {finished.length > 0 && (
        <Glass as="section" className="widget" style={{ minHeight: 0, marginTop: 16 }} aria-label="Finished projects">
          <header className="widget__head"><CheckCircle2 aria-hidden="true" /><span>Finished</span></header>
          <ul className="items">{done.shown.map((p) => <ProjectRow key={p.title} project={p} />)}</ul>
          {done.toggle}
        </Glass>
      )}
    </>
  );
}

function ProjectRow({ project: p }: { project: ProjectSummary }) {
  const due = dueWords(p.days_left);
  const bits = [due, p.open_tasks ? `${p.open_tasks} open task${p.open_tasks === 1 ? "" : "s"}` : null, p.days_idle ? `quiet ${p.days_idle} days` : null].filter(Boolean);
  return (
    <li>
      <Link className="item" to={`/projects/${encodeURIComponent(p.title)}`}>
        <span className={`item__dot ${p.days_left != null && p.days_left < 0 ? "dot-critical" : p.days_left != null && p.days_left <= 7 ? "dot-warning" : p.days_idle ? "" : "dot-good"}`} aria-hidden="true" />
        <span className="item__text">
          <div className="item__title">{p.title}</div>
          <div className="item__subtitle">{bits.join(" · ") || (FINISHED.includes(p.status) ? "Finished" : "Nothing due")}</div>
        </span>
      </Link>
    </li>
  );
}

/** One project: the note, its tasks, meetings and emails, from everywhere (4.0). */
export function ProjectScreen() {
  const title = decodeURIComponent(useParams().title ?? "");
  const { data, error, loading, reload } = useResource(`siris-project:${title}`, () => projects.get(title), { staleMs: 60_000, persist: true });
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => {
    document.title = `${title} · SirisOS`;
  }, [title]);

  async function add(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    try {
      await projects.addTask(title, text.trim());
      setText("");
      await reload(true);
    } catch (err) {
      setNote(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }
  async function tick(t: TaskItem) {
    await tasks.done(t).catch((err) => setNote(err.message));
    await reload(true).catch(() => undefined);
  }
  async function finish() {
    setBusy(true);
    try {
      await projects.finish(title);
      setNote("Marked finished in Siris.");
      await reload(true);
    } catch (err) {
      setNote(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow"><Link to="/projects">Projects</Link>{data?.areas.length ? ` · ${data.areas.join(", ")}` : ""}</p>
          <h1 className="page-head__title">{data?.title ?? title}</h1>
        </div>
      </header>
      {error && !data && <div className="error-banner" role="alert">{error}</div>}
      {!data && loading && <div className="skeleton" style={{ height: 240, marginTop: 16 }} />}
      {data && <ProjectBody page={data} text={text} setText={setText} busy={busy} add={add} tick={tick} finish={finish} note={note} />}
    </>
  );
}

function ProjectBody({ page: p, text, setText, busy, add, tick, finish, note }: {
  page: ProjectPage; text: string; setText: (s: string) => void; busy: boolean; add: (e: FormEvent) => void; tick: (t: TaskItem) => void; finish: () => void; note: string | null;
}) {
  const related = useShowMore([...new Set([...p.links, ...p.backlinks])]);
  const emails = useShowMore(p.emails);
  const due = p.deadline ? dueWords(p.deadline.days_left) : null;
  const finished = FINISHED.includes(p.status);
  const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "");
  return (
    <div className="stack" style={{ marginTop: 16 }}>
      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="About">
        <header className="widget__head"><FolderKanban aria-hidden="true" /><span>{finished ? "Finished" : due ?? "Active"}</span>
          {!finished && <button type="button" className="button button--small" style={{ marginLeft: "auto" }} disabled={busy} onClick={finish}>Mark finished</button>}
        </header>
        {p.about ? <p style={{ margin: 0 }}>{p.about}</p> : <p className="muted" style={{ margin: 0 }}>The note doesn't say much yet.</p>}
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          {[p.days_idle ? `Not touched in ${p.days_idle} days` : null, p.updated ? `Updated ${p.updated}` : null, p.source].filter(Boolean).join(" · ")}
          {" · "}<Link to={`/brain?q=${encodeURIComponent(p.title)}`}>Open in Siris</Link>
        </p>
        {note && <p className="muted" role="status" style={{ margin: 0, fontSize: 14 }}>{note}</p>}
      </Glass>

      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Open tasks">
        <header className="widget__head"><Circle aria-hidden="true" /><span>Open tasks</span></header>
        {p.tasks.length === 0 && <p className="muted" style={{ margin: 0, fontSize: 14 }}>Nothing open.</p>}
        <ul className="items">
          {p.tasks.map((t) => (
            <li key={t.id} className="item">
              <button type="button" className="icon-link" aria-label={`Mark "${t.title}" done`} onClick={() => tick(t)}><Circle size={16} aria-hidden="true" /></button>
              <span className="item__text"><div className="item__title">{t.title}</div><div className="item__subtitle">{[dueLabel(t), t.source === "siris" ? "In the note" : t.source === "reminder" ? "Reminder" : "SirisOS"].filter(Boolean).join(" · ")}</div></span>
            </li>
          ))}
        </ul>
        <form className="row" style={{ gap: 6 }} onSubmit={add}>
          <input className="field" value={text} onChange={(e) => setText(e.target.value)} placeholder="Add a task, e.g. send levels friday" aria-label="New task for this project" />
          <button type="submit" className="button button--small button--primary" disabled={busy || !text.trim()} aria-label="Add task"><Plus size={15} aria-hidden="true" /></button>
        </form>
      </Glass>

      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Meetings">
        <header className="widget__head"><CalendarDays aria-hidden="true" /><span>Meetings</span></header>
        {p.meetings.upcoming.length + p.meetings.recent.length === 0 ? (
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>{p.unavailable.includes("calendar") ? "The calendar didn't answer." : `None in the calendar naming ${p.names.join(" or ")}.`}</p>
        ) : (
          <ul className="items">
            {p.meetings.upcoming.map((e, i) => (
              <li key={`u${i}`}>
                <Link className="item" to={`/meeting?title=${encodeURIComponent(e.title)}&start=${encodeURIComponent(e.start ?? "")}`}>
                  <span className="item__dot dot-good" aria-hidden="true" />
                  <span className="item__text"><div className="item__title">{e.title}</div><div className="item__subtitle">{when(e.start)} · Prepare</div></span>
                </Link>
              </li>
            ))}
            {p.meetings.recent.map((e, i) => (
              <li key={`r${i}`} className="item">
                <span className="item__dot" aria-hidden="true" />
                <span className="item__text"><div className="item__title">{e.title}</div><div className="item__subtitle">{when(e.start)}</div></span>
              </li>
            ))}
          </ul>
        )}
      </Glass>

      <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Emails">
        <header className="widget__head"><Mail aria-hidden="true" /><span>Emails</span></header>
        {p.emails.length === 0 ? (
          <p className="muted" style={{ margin: 0, fontSize: 14 }}>
            {p.guest_mode ? "Hidden in guest mode." : p.unavailable.includes("email") ? "Email didn't answer (SirisAI 2.25 or later searches it)." : !p.email_configured ? "Email isn't set up in SirisAI." : "None in the last 90 days with the project's name in the subject."}
          </p>
        ) : (
          <ul className="items">
            {emails.shown.map((m) => (
              <li key={m.uid} className="item">
                <span className="item__text"><div className="item__title">{m.subject}</div><div className="item__subtitle">{m.sender}{m.date ? ` · ${new Date(m.date).toLocaleDateString(undefined, { day: "numeric", month: "short" })}` : ""} · {m.snippet}</div></span>
              </li>
            ))}
          </ul>
        )}
        {emails.toggle}
      </Glass>

      {related.shown.length > 0 && (
        <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Linked notes">
          <header className="widget__head"><Link2 aria-hidden="true" /><span>Linked notes</span></header>
          <ul className="items">
            {related.shown.map((n) => (
              <li key={n}><Link className="item" to={`/brain?q=${encodeURIComponent(n)}`}><span className="item__text"><div className="item__title">{n}</div></span></Link></li>
            ))}
          </ul>
          {related.toggle}
        </Glass>
      )}
    </div>
  );
}
