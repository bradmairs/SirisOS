import { useState } from "react";
import { CheckCheck } from "lucide-react";
import { ApiError } from "../api/client";
import { brain, type BrainReviewItem } from "../api/hub";
import type { BrainNote } from "../api/types";
import { refreshResource, useResource } from "../api/resource";
import { Glass } from "../components/Glass";
import { NoteEditor } from "./NoteEdit";

/**
 * "Is this right?" (11.6.0): one note Siris wrote at a time, the most linked first, with what Siris
 * thinks is true. "Right" marks it checked (Siris then trusts it a little more); "Fix it" opens the note
 * to edit, and saving the fix counts as checking it; "Not now" moves on. None of Siris' 240 notes had
 * been checked: the weekly chat message asking about three went unanswered, as the debrief did before
 * it became a card. Hidden when there's nothing to check or SirisAI can't be reached.
 */
export function ReviewCard() {
  const res = useResource("brain:review", () => brain.review(5).catch((e) => {
    if (e instanceof ApiError && (e.status === 404 || e.status === 503)) return [] as BrainReviewItem[];
    throw e;
  }), { staleMs: 30 * 60_000 });
  const [skipped, setSkipped] = useState<string[]>([]);
  const [done, setDone] = useState<string[]>([]);
  const [editing, setEditing] = useState<BrainNote | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queue = (res.data ?? []).filter((n) => !skipped.includes(n.title) && !done.includes(n.title));
  const note = queue[0];
  if (!note) {
    return done.length ? (
      <Glass as="section" className="widget review-card" style={{ minHeight: 0, marginTop: 14 }} aria-label="Is this right?">
        <header className="widget__head"><CheckCheck aria-hidden="true" /><span>Is this right?</span></header>
        <p className="tone-good" role="status" style={{ margin: 0 }}>Thanks: {done.length} checked. Siris trusts those more now.</p>
      </Glass>
    ) : null;
  }

  async function markRight(title: string) {
    setBusy(true);
    setError(null);
    try {
      await brain.reviewed(title);
      setDone((d) => [...d, title]);
      setEditing(null);
      if (queue.length <= 1) refreshResource("brain:review");
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't save.");
    } finally {
      setBusy(false);
    }
  }

  async function openEditor() {
    setError(null);
    try {
      setEditing(await brain.note(note.title));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't open the note.");
    }
  }

  // The card reads "Title (details) — what's true now — Newest (date): …": show the details apart.
  const card = (note.card ?? `${note.title} — ${note.excerpt}`).slice(note.title.length).trim();
  const details = card.match(/^\((.*?)\)\s*/)?.[1] ?? "";
  const text = card.slice(details ? details.length + 2 : 0).replace(/^\s*—\s*/, "");
  return (
    <Glass as="section" className="widget review-card" style={{ minHeight: 0, marginTop: 14 }} aria-label="Is this right?">
      <header className="widget__head"><CheckCheck aria-hidden="true" /><span>Is this right?</span></header>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>
        Siris wrote this note. Check it so wrong facts don't spread{queue.length > 1 ? ` (${queue.length} waiting)` : ""}.
      </p>
      <div className="review-card__note">
        <strong>{note.title}</strong>
        {details && <p className="muted" style={{ margin: "2px 0 0", fontSize: 12 }}>{details}</p>}
        <p style={{ margin: "4px 0 0", fontSize: 14 }}>{text}</p>
        {note.as_of && <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }}>As of {note.as_of} · {note.links} links</p>}
      </div>
      {error && <div className="error-banner" role="alert">{error}</div>}
      {editing ? (
        <NoteEditor note={editing} onCancel={() => setEditing(null)} onSaved={() => markRight(note.title)} />
      ) : (
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <Glass as="button" type="button" shape="pill" interactive className="button button--small button--primary"
            onClick={() => markRight(note.title)} disabled={busy}>{busy ? "Saving…" : "Right"}</Glass>
          <button type="button" className="button button--small" onClick={openEditor} disabled={busy}>Fix it</button>
          <button type="button" className="chip chip--button" onClick={() => setSkipped((s) => [...s, note.title])} disabled={busy}>Not now</button>
        </div>
      )}
    </Glass>
  );
}
