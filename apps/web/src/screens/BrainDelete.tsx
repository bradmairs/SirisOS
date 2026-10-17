import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { brain } from "../api/hub";
import type { BrainDeleteResult } from "../api/types";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

/**
 * Delete a Siris note, after a confirmation that says what will happen. By default the note
 * moves out of the brain (search, links and the map) and can be restored; "permanently" removes it.
 */
export function DeleteNoteButton({
  title,
  compact = false,
  onDeleted,
}: {
  title: string;
  compact?: boolean;
  onDeleted: (result: BrainDeleteResult) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      {compact ? (
        <button type="button" className="icon-link" onClick={() => setOpen(true)} aria-label={`Delete ${title}`} title="Delete">
          <Trash2 size={15} aria-hidden="true" />
        </button>
      ) : (
        <button type="button" className="chip chip--button delete-chip" onClick={() => setOpen(true)} aria-label={`Delete ${title}`}>
          <Trash2 size={13} aria-hidden="true" /> Delete
        </button>
      )}
      {open && (
        <DeleteNoteSheet
          title={title}
          onClose={() => setOpen(false)}
          onDeleted={(r) => {
            setOpen(false);
            onDeleted(r);
          }}
        />
      )}
    </>
  );
}

function DeleteNoteSheet({ title, onClose, onDeleted }: { title: string; onClose: () => void; onDeleted: (r: BrainDeleteResult) => void }) {
  const [backlinks, setBacklinks] = useState<number | null>(null);
  const [permanent, setPermanent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    brain
      .note(title)
      .then((n) => live && setBacklinks(n.backlinks.filter((t) => t !== n.title).length))
      .catch(() => live && setBacklinks(null));
    return () => {
      live = false;
    };
  }, [title]);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      onDeleted(await brain.remove(title, permanent));
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
      setBusy(false);
    }
  }

  return (
    <Sheet label={`Delete ${title}`} onClose={onClose}>
      <div className="stack">
        <h2 className="app-sheet__name">Delete “{title}”?</h2>
        <p className="muted" style={{ margin: 0 }}>
          It leaves Siris: search, links and the mind map.
          {backlinks !== null && backlinks > 0 && ` ${plural(backlinks, "other note")} link${backlinks === 1 ? "s" : ""} to it; those links are removed, but their words stay.`}
          {!permanent && " You can restore it from Recently deleted."}
        </p>
        <label className="row delete-permanent">
          <input type="checkbox" checked={permanent} onChange={(e) => setPermanent(e.target.checked)} />
          <span>Delete permanently (can't be restored here)</span>
        </label>
        {error && <div className="error-banner" role="alert">{error}</div>}
        <div className="row">
          <span className="spacer" />
          <Glass as="button" type="button" shape="pill" interactive className="button button--small" onClick={onClose}>
            Cancel
          </Glass>
          <Glass as="button" type="button" shape="pill" interactive className="button button--small button--danger" onClick={confirm} disabled={busy}>
            <Trash2 aria-hidden="true" /> {busy ? "Deleting…" : permanent ? "Delete permanently" : "Delete"}
          </Glass>
        </div>
      </div>
    </Sheet>
  );
}
