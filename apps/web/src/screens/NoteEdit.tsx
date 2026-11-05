import { useState } from "react";
import { Pencil } from "lucide-react";
import { brain } from "../api/hub";
import type { BrainNote } from "../api/types";

/** Edit a note's text (7.2): Brad's words replace it, through the brain engine, which keeps the
 *  frontmatter, links new mentions and refuses the edit if the note changed since it was opened. */
export function NoteEditor({ note, onSaved, onCancel }: { note: BrainNote; onSaved: (r: { links_added: string[] }) => void; onCancel: () => void }) {
  const [text, setText] = useState(note.body ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      onSaved(await brain.edit(note.title, text, note.version));
    } catch (err) {
      setError(err instanceof Error ? err.message.replace(/^SirisAI: /, "") : "Couldn't save it.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="stack note-edit" style={{ gap: 8 }}>
      <textarea className="field note-edit__text" aria-label={`Text of ${note.title}`} value={text} onChange={(e) => setText(e.target.value)}
        rows={Math.min(24, Math.max(8, text.split("\n").length + 2))} spellCheck />
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>Markdown. [[Links]] to other notes work; new mentions of other notes' titles are linked when you save. The old text stays in the brain's history.</p>
      {error && <p className="tone-critical" role="alert" style={{ margin: 0, fontSize: 13 }}>{error}</p>}
      <div className="row" style={{ gap: 8 }}>
        <button type="button" className="button button--primary" disabled={busy || !text.trim() || text === note.body} onClick={save}>{busy ? "Saving…" : "Save"}</button>
        <button type="button" className="button" disabled={busy} onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

export function EditNoteButton({ onClick }: { onClick: () => void }) {
  return <button type="button" className="chip chip--button" onClick={onClick}><Pencil size={12} aria-hidden="true" /> Edit</button>;
}
