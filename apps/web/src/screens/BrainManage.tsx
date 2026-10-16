import { useEffect, useState } from "react";
import { BrainCircuit, RotateCcw, Search, Trash2, Undo2 } from "lucide-react";
import { brain, memories } from "../api/hub";
import { useResource } from "../api/resource";
import type { BrainDeleted, SirisMemory } from "../api/types";
import { Glass } from "../components/Glass";

const dayLabel = (iso: string) => {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
};

/** The shared "recently deleted" list: the Brain screen reloads it after a delete. */
export function useDeletedNotes() {
  return useResource<BrainDeleted[]>("brain:deleted", () => brain.deleted(), { staleMs: 30_000 });
}

/** Housekeeping for the brain: Siris's own memories, and notes deleted recently. */
export function BrainManage({ onRestored }: { onRestored?: (title: string) => void }) {
  return (
    <section aria-labelledby="manage-title">
      <h2 id="manage-title" className="section-title">Manage</h2>
      <div className="widget-grid">
        <MemoriesPanel />
        <DeletedPanel onRestored={onRestored} />
      </div>
    </section>
  );
}

/** What Siris saved with `remember`. The brain keeps its own copy of most of these as notes, so
 *  deleting a memory stops Siris recalling it; delete the note too to take it out of the brain. */
function MemoriesPanel() {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<SirisMemory[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const timer = window.setTimeout(() => {
      memories
        .list(q)
        .then((m) => {
          if (!live) return;
          setItems(m);
          setError(null);
        })
        .catch((err) => live && setError(err instanceof Error ? err.message : "Couldn't load Siris's memories."));
    }, q ? 300 : 0);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [q]);

  async function remove(m: SirisMemory) {
    setBusy(m.id);
    try {
      await memories.remove(m.id);
      setItems((all) => (all ?? []).filter((x) => x.id !== m.id));
      setDone(`Deleted: “${m.content.length > 60 ? `${m.content.slice(0, 60)}…` : m.content}”`);
      setConfirming(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Glass className="widget" aria-label="Siris's memories">
      <div className="widget__head">
        <BrainCircuit aria-hidden="true" /> Siris's memories
      </div>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        What Siris saved from your chats. Deleting one stops Siris recalling it, and can't be undone.
      </p>
      <label className="mini-search">
        <Search size={14} aria-hidden="true" />
        <input placeholder="Find a memory" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Find a memory" />
      </label>
      {done && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{done}</p>}
      {error && <p className="tone-critical" style={{ margin: 0 }}>{error}</p>}
      {items === null && !error ? (
        <div className="skeleton" style={{ height: 60 }} />
      ) : items && items.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>{q ? "No memories match." : "Siris hasn't saved any memories yet."}</p>
      ) : (
        <ul className="items manage__list">
          {(items ?? []).map((m) => (
            <li key={m.id} className="item">
              <span className="item__text">
                <div className="item__title manage__memory">{m.content}</div>
                <div className="item__subtitle">
                  Saved {dayLabel(m.created_at)}
                  {m.recall_count > 0 && ` · recalled ${m.recall_count} time${m.recall_count === 1 ? "" : "s"}`}
                </div>
              </span>
              {confirming === m.id ? (
                <span className="manage__confirm">
                  <button type="button" className="chip chip--button delete-chip" onClick={() => remove(m)} disabled={busy === m.id}>
                    {busy === m.id ? "…" : "Delete"}
                  </button>
                  <button type="button" className="chip chip--button" onClick={() => setConfirming(null)}>Keep</button>
                </span>
              ) : (
                <button type="button" className="icon-link" onClick={() => setConfirming(m.id)} aria-label={`Delete memory: ${m.content}`} title="Delete">
                  <Trash2 size={15} aria-hidden="true" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </Glass>
  );
}

function DeletedPanel({ onRestored }: { onRestored?: (title: string) => void }) {
  const res = useDeletedNotes();
  const [busy, setBusy] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const items = res.data ?? null;

  async function act(d: BrainDeleted, kind: "restore" | "purge") {
    setBusy(d.title);
    setError(null);
    try {
      if (kind === "restore") {
        await brain.restore(d.title);
        setDone(`Restored ${d.title}`);
        onRestored?.(d.title);
      } else {
        await brain.purge(d.title);
        setDone(`Deleted ${d.title} permanently`);
      }
      setConfirming(null);
      res.mutate((items ?? []).filter((x) => x !== d));
      res.reload(true).catch(() => undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Glass className="widget" aria-label="Recently deleted">
      <div className="widget__head">
        <Trash2 aria-hidden="true" /> Recently deleted
      </div>
      {done && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{done}</p>}
      {(error || (!items && res.error)) && <p className="tone-critical" style={{ margin: 0 }}>{error ?? res.error}</p>}
      {items === null && !res.error ? (
        <div className="skeleton" style={{ height: 40 }} />
      ) : items && items.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>Nothing deleted.</p>
      ) : (
        <ul className="items manage__list">
          {(items ?? []).map((d) => (
            <li key={`${d.title}-${d.date}`} className="item">
              <span className="item__text">
                <div className="item__title">{d.title}</div>
                <div className="item__subtitle">
                  {d.restorable ? `Deleted ${dayLabel(d.date)} · from ${d.path}` : `Deleted permanently ${dayLabel(d.date)}`}
                </div>
              </span>
              {d.restorable &&
                (confirming === d.title ? (
                  <span className="manage__confirm">
                    <button type="button" className="chip chip--button delete-chip" onClick={() => act(d, "purge")} disabled={busy !== null}>
                      {busy === d.title ? "…" : "Delete forever"}
                    </button>
                    <button type="button" className="chip chip--button" onClick={() => setConfirming(null)}>Keep</button>
                  </span>
                ) : (
                  <span className="manage__confirm">
                    <button type="button" className="chip chip--button" onClick={() => act(d, "restore")} disabled={busy !== null} aria-label={`Restore ${d.title}`}>
                      <RotateCcw size={13} aria-hidden="true" /> {busy === d.title ? "…" : "Restore"}
                    </button>
                    <button type="button" className="icon-link" onClick={() => setConfirming(d.title)} aria-label={`Delete ${d.title} forever`} title="Delete forever">
                      <Trash2 size={15} aria-hidden="true" />
                    </button>
                  </span>
                ))}
            </li>
          ))}
        </ul>
      )}
    </Glass>
  );
}

/** The bar shown after a delete, with Undo while the note can still be restored. */
export function DeletedBar({ title, permanent, onUndone, onClose }: { title: string; permanent: boolean; onUndone: () => void; onClose: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function undo() {
    setBusy(true);
    try {
      await brain.restore(title);
      onUndone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't undo that.");
      setBusy(false);
    }
  }
  return (
    <Glass className="deleted-bar" role="status">
      <Trash2 size={16} aria-hidden="true" />
      <span className="deleted-bar__text">{error ?? `Deleted ${title}${permanent ? " permanently" : ""}`}</span>
      {!permanent && !error && (
        <button type="button" className="chip chip--button" onClick={undo} disabled={busy}>
          <Undo2 size={13} aria-hidden="true" /> {busy ? "…" : "Undo"}
        </button>
      )}
      <button type="button" className="icon-link" onClick={onClose} aria-label="Dismiss">×</button>
    </Glass>
  );
}
