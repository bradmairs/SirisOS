import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Brain, PenLine } from "lucide-react";
import { brain } from "../api/hub";
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
      setNote({ ok: false, text: err instanceof Error ? err.message : "Couldn't save." });
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
