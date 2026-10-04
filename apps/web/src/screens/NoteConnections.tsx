import { useState } from "react";
import { Link2, Unlink } from "lucide-react";
import { brain } from "../api/hub";
import type { BrainNote } from "../api/types";

/** A note's links, both directions, each with an Unlink. Unlinking removes the link both
 *  ways (the words stay, just not as a link) and Siris never links the pair again. */
export function NoteConnections({ title }: { title: string }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState<BrainNote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function load() {
    try {
      setNote(await brain.note(title));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't load this note's connections.");
    }
  }

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && !note) await load();
  }

  async function unlink(other: string) {
    setBusy(other);
    try {
      await brain.unlink(title, other);
      setDone(`Unlinked ${other}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
    } finally {
      setBusy(null);
    }
  }

  const connected = note ? [...new Set([...note.links, ...note.backlinks])].filter((t) => t !== note.title).sort((a, b) => a.localeCompare(b)) : [];

  return (
    <div className="connections">
      <button type="button" className="chip chip--button" onClick={toggle} aria-expanded={open}>
        <Link2 size={13} aria-hidden="true" /> {open ? "Hide connections" : "Connections"}
      </button>
      {open && (
        <div className="connections__body">
          {error && <p className="tone-critical" style={{ margin: 0 }}>{error}</p>}
          {done && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{done}</p>}
          {!note && !error && <div className="skeleton" style={{ height: 28 }} />}
          {note && connected.length === 0 && <p className="muted" style={{ margin: 0 }}>Not linked to anything yet.</p>}
          {connected.length > 0 && (
            <ul className="items">
              {connected.map((other) => (
                <li key={other} className="item">
                  <span className="item__dot" style={{ background: "#a78bfa" }} aria-hidden="true" />
                  <span className="item__text"><div className="item__title">{other}</div></span>
                  <button type="button" className="icon-link" disabled={busy !== null} onClick={() => unlink(other)}
                    aria-label={`Unlink ${title} and ${other}`} title="Unlink">
                    {busy === other ? "…" : <Unlink size={15} aria-hidden="true" />}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
