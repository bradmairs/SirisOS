import { useState } from "react";
import { NotebookPen } from "lucide-react";
import { gym, type NoteAction } from "../api/gym";
import { Glass } from "../components/Glass";

/** What a session note asked for (11.14), each to approve or leave: spare a sore area, swap an exercise at a gym, or
 * a step up or down next time. Nothing changes without a tap. */
export function NoteActionList({ actions, onChange }: { actions: NoteAction[]; onChange?: (left: NoteAction[]) => void }) {
  const [left, setLeft] = useState(actions);
  const [said, setSaid] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  if (!left.length && !said) return null;
  const answer = async (a: NoteAction, act: "apply" | "dismiss") => {
    setBusy(a.id);
    try {
      const out = await gym.noteAction(a.id, act);
      const rest = left.filter((x) => x.id !== a.id);
      setLeft(rest);
      setSaid(out.done || null);
      onChange?.(rest);
    } catch (e) {
      setSaid(e instanceof Error ? e.message : "Couldn't do that.");
    } finally { setBusy(null); }
  };
  return (
    <div className="stack" style={{ gap: 8 }}>
      <ul className="items" aria-label="From your note">
        {left.map((a) => (
          <li key={a.id} className="item gym-note-action">
            <span className="item__text"><span className="item__title" style={{ whiteSpace: "normal" }}>{a.text}</span>
              {a.quote && <span className="item__subtitle" style={{ whiteSpace: "normal" }}>“{a.quote}”</span>}</span>
            <span className="row" style={{ gap: 6 }}>
              <button type="button" className="button button--primary button--small" disabled={busy === a.id} onClick={() => void answer(a, "apply")}>Do it</button>
              <button type="button" className="chip chip--button" disabled={busy === a.id} onClick={() => void answer(a, "dismiss")}>No</button>
            </span>
          </li>
        ))}
      </ul>
      {said && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{said}</p>}
    </div>
  );
}

/** A note on the workout just finished (11.14): typed or dictated, read at once for what it asks. */
export function DoneNote({ session, initial }: { session: string; initial: NoteAction[] }) {
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actions, setActions] = useState<NoteAction[]>(initial);
  const [key, setKey] = useState(0);  // a fresh list for each lot of suggestions
  const save = async () => {
    setBusy(true);
    try {
      const out = await gym.setNote(session, note);
      setSaved(true);
      if (out.note_actions.length) { setActions(out.note_actions); setKey((k) => k + 1); }
    } finally { setBusy(false); }
  };
  return (
    <div className="stack" style={{ gap: 6 }}>
      {!saved ? (
        <form className="stack" style={{ gap: 6 }} onSubmit={(e) => { e.preventDefault(); if (note.trim()) void save(); }}>
          <label className="muted" style={{ fontSize: 13 }} htmlFor="done-note">Anything to note? Something sore, gear taken, a lift that felt easy or too heavy.</label>
          <textarea id="done-note" className="field" rows={2} value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Left shoulder twinged on the press" />
          <button type="submit" className="chip chip--button" style={{ alignSelf: "flex-start" }} disabled={busy || !note.trim()}>{busy ? "Saving…" : "Save the note"}</button>
        </form>
      ) : <p className="muted" style={{ margin: 0, fontSize: 13 }}>Note saved.{actions.length ? "" : " Nothing in it to act on."}</p>}
      {actions.length > 0 && <NoteActionList key={key} actions={actions} />}
    </div>
  );
}

/** On Today (11.14): what recent notes asked for and is still waiting for an answer. */
export function NoteActionsCard({ actions, onChange }: { actions: NoteAction[]; onChange: () => void }) {
  if (!actions.length) return null;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="From your notes">
      <header className="widget__head"><NotebookPen aria-hidden="true" /><span>From your notes</span></header>
      <NoteActionList actions={actions} onChange={() => onChange()} />
    </Glass>
  );
}
