import { useEffect, useState } from "react";
import { Brain as BrainIcon, ChevronDown } from "lucide-react";
import { brain } from "../api/hub";
import { useResource } from "../api/resource";
import type { BrainDeleteResult, BrainHit, BrainNote } from "../api/types";
import { Glass } from "../components/Glass";
import { NoteBody } from "../components/NoteBody";
import { DeleteNoteButton } from "./BrainDelete";
import { NoteConnections } from "./NoteConnections";

const LINKS_SHOWN = 12;

/** What a note says, for reading: without its own title line, or the Connections list the brain
 *  keeps at the end (shown as links instead). */
export function readable(body: string, title: string): string {
  const text = body.replace(/^\s*# .*\n?/, (h) => (h.trim().slice(2).trim().toLowerCase() === title.toLowerCase() ? "" : h));
  return text.split(/^#{1,3} (?:Connections|Related)\s*$/m)[0].trim();
}

/** A search result: its matching lines, then the whole note when you tap it (4.93). Its
 *  [[links]] and connected notes open those notes. */
export function NoteHit({ hit, onOpen, onDeleted, start = false }: {
  hit: BrainHit; onOpen: (title: string) => void; onDeleted: (r: BrainDeleteResult) => void; start?: boolean;
}) {
  const [open, setOpen] = useState(start);
  const [allLinks, setAllLinks] = useState(false);
  useEffect(() => { if (start) setOpen(true); }, [start]);
  const note = useResource<BrainNote>(`brain:note:${hit.title}`, () => brain.note(hit.title), { enabled: open, staleMs: 60_000 });
  const n = note.data;
  const connected = n ? [...new Set([...n.links, ...n.backlinks])].filter((t) => t.toLowerCase() !== hit.title.toLowerCase()).sort((a, b) => a.localeCompare(b)) : [];
  const id = `note-${(hit.path ?? hit.title).replace(/[^a-z0-9]+/gi, "-")}`;

  return (
    <Glass className={`widget note-hit${open ? " note-hit--open" : ""}`} style={{ minHeight: 0 }}>
      <button type="button" className="widget__head note-hit__head" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
        <BrainIcon style={{ color: "#a78bfa" }} aria-hidden="true" />
        <span className="note-hit__title">{hit.title}</span>
        {hit.type && <span className="chip">{hit.type}</span>}
        <ChevronDown size={16} className="note-hit__chevron" aria-hidden="true" />
      </button>
      {!open && (hit.excerpts ?? []).slice(0, 2).map((x, i) => (
        <p key={i} className="muted" style={{ margin: 0 }}>{x}</p>
      ))}
      {open && (
        <div id={id} className="note-hit__body">
          {!n && !note.error && <div className="skeleton" style={{ height: 80 }} />}
          {!n && note.error && <p className="tone-critical" style={{ margin: 0 }}>Couldn't open this note: {note.error}</p>}
          {n && (
            <>
              {n.body && readable(n.body, n.title) ? <NoteBody text={readable(n.body, n.title)} onOpen={onOpen} /> : <p className="muted" style={{ margin: 0 }}>This note has no text yet.</p>}
              {(n.tags?.length || n.as_of) && (
                <p className="muted note-hit__meta">
                  {n.as_of && <>Updated {new Date(`${n.as_of}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</>}
                  {n.as_of && n.tags?.length ? " · " : ""}
                  {n.tags?.map((t) => `#${t}`).join(" ")}
                </p>
              )}
              {connected.length > 0 && (
                <div className="note-hit__links" aria-label="Connected notes">
                  <span className="muted" style={{ fontSize: 13 }}>Connected:</span>
                  {(allLinks ? connected : connected.slice(0, LINKS_SHOWN)).map((t) => (
                    <button key={t} type="button" className="chip chip--button" onClick={() => onOpen(t)}>{t}</button>
                  ))}
                  {connected.length > LINKS_SHOWN && (
                    <button type="button" className="show-more" onClick={() => setAllLinks(!allLinks)}>
                      {allLinks ? "Fewer" : `and ${connected.length - LINKS_SHOWN} more`}
                    </button>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
      {hit.path && <p className="muted" style={{ margin: 0, fontSize: 12 }}>{hit.path}</p>}
      <div className="row note-actions">
        <NoteConnections title={hit.title} />
        <DeleteNoteButton title={hit.title} onDeleted={onDeleted} />
      </div>
    </Glass>
  );
}
