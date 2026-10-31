import { keep, unreachable } from "../api/outbox";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Brain, History, PenLine } from "lucide-react";
import { brain } from "../api/hub";
import { ago, resurface } from "../api/resurface";
import { useResource } from "../api/resource";
import { isTaskText, tasks } from "../api/tasks";
import type { Hud } from "../api/types";
import { Glass } from "../components/Glass";

/** What Siris learned or updated today (4.9): at work, and winding down. */
export function BrainTodayWidget({ items }: { items: NonNullable<Hud["brain"]> }) {
  return (
    <Glass as="section" className="widget" aria-label="Learned today">
      <header className="widget__head"><Brain aria-hidden="true" /><span>Learned today</span>
        <Link to="/brain" className="widget__source">Brain</Link></header>
      {items.length === 0 ? <p className="muted" style={{ margin: 0 }}>Nothing new in the brain today.</p> : (
        <ul className="items">
          {items.slice(0, 5).map((n) => (
            <li key={n.title} className="item">
              <span className="item__dot" aria-hidden="true" />
              <span className="item__text"><Link to={`/brain?q=${encodeURIComponent(n.title)}`} className="item__title">{n.title}</Link>
                <div className="item__subtitle">{n.action}</div></span>
            </li>
          ))}
        </ul>
      )}
    </Glass>
  );
}

/** One older note a day, related to what you're working on (5.1). Hidden when there's none. */
export function ResurfaceWidget() {
  const res = useResource("resurface", () => resurface.today(), { staleMs: 30 * 60_000, persist: true });
  const [busy, setBusy] = useState(false);
  const note = res.data?.note;
  if (!note) return null;
  async function answer(kind: "seen" | "not_useful") {
    if (!note) return;
    setBusy(true);
    try {
      res.mutate(await resurface.respond(note.title, kind));
    } finally {
      setBusy(false);
    }
  }
  const when = ago(note.age_days);
  return (
    <Glass as="section" className="widget" aria-label="From your notes">
      <header className="widget__head"><History aria-hidden="true" /><span>From your notes</span>
        {when && <span className="widget__source">{when}</span>}</header>
      <Link to={`/brain?q=${encodeURIComponent(note.title)}`} className="item__title resurface__title">{note.title}</Link>
      {note.excerpt && <p className="resurface__excerpt">{note.excerpt}</p>}
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>{note.why}</p>
      <div className="row" style={{ gap: 6, marginTop: 4 }}>
        <Link to={`/brain?q=${encodeURIComponent(note.title)}`} className="button button--small button--primary">Read it</Link>
        <button type="button" className="button button--small" disabled={busy} onClick={() => answer("seen")}>Seen it</button>
        <button type="button" className="button button--small" disabled={busy} onClick={() => answer("not_useful")}>Not useful</button>
      </div>
    </Glass>
  );
}

/** Empty your head before bed (4.9): a thought goes to the brain's inbox, "remind me to…" to your tasks. */
export function CaptureWidget() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    setBusy(true);
    try {
      if (isTaskText(value)) {
        const made = await tasks.add({ text: value });
        setNote({ ok: true, text: `Added to your tasks: “${made.title}”.` });
      } else {
        const r = await brain.capture({ text: value });
        setNote({ ok: true, text: `Saved to Siris: “${r.title}”.` });
      }
      setText("");
    } catch (err) {
      if (unreachable(err) && keep(isTaskText(value) ? { kind: "task", text: value } : { kind: "capture", body: { text: value } })) {
        setNote({ ok: true, text: "Kept on this phone: it goes to SirisOS as soon as it can reach it." });
        setText("");
      } else {
        setNote({ ok: false, text: err instanceof Error ? err.message : "Couldn't save." });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Glass as="section" className="widget" aria-label="Quick capture">
      <header className="widget__head"><PenLine aria-hidden="true" /><span>On your mind?</span></header>
      <form onSubmit={save} className="stack" style={{ gap: 8 }}>
        <textarea className="field" rows={3} value={text} onChange={(e) => setText(e.target.value)} aria-label="Capture a thought"
          placeholder="A thought, or “remind me to…”" />
        <div className="row"><button type="submit" className="button button--small" disabled={busy || !text.trim()}>{busy ? "Saving…" : "Save"}</button></div>
      </form>
      {note && <p className={note.ok ? "tone-good" : "tone-critical"} role="status" style={{ margin: 0, fontSize: 13 }}>{note.text}</p>}
    </Glass>
  );
}
