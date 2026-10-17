import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { Brain as BrainIcon, Check, Search } from "lucide-react";
import { brain } from "../api/hub";
import { useResource } from "../api/resource";
import type { BrainHit } from "../api/types";
import { Glass } from "../components/Glass";
import { useShowMore } from "../components/ShowMore";
import type { BrainDeleteResult } from "../api/types";
import { DeleteNoteButton } from "./BrainDelete";
import { BrainInsights } from "./BrainInsights";
import { BrainManage, DeletedBar, useDeletedNotes } from "./BrainManage";
import { BrainMap } from "./BrainMap";
import { NoteConnections } from "./NoteConnections";

export function Brain() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<BrainHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const todayRes = useResource("brain:today", () => brain.today(), { refreshMs: 120_000 });
  const deletedRes = useDeletedNotes();
  // The activity log still says a deleted note was learned today; don't list it.
  const gone = new Set((deletedRes.data ?? []).map((d) => d.title.toLowerCase()));
  const today = todayRes.data ? todayRes.data.items.filter((i) => !gone.has(i.title.toLowerCase())) : null;
  const learned = useShowMore(today ?? []);
  const [lastDeleted, setLastDeleted] = useState<{ title: string; permanent: boolean } | null>(null);
  const [searchNonce, setSearchNonce] = useState(0);
  const [capture, setCapture] = useState("");
  const [saved, setSaved] = useState<string | null>(null);

  // Search everything opens a note here with ?q=.
  const [params] = useSearchParams();
  useEffect(() => {
    const wanted = params.get("q");
    if (wanted) setQ(wanted);
  }, [params]);

  useEffect(() => {
    const query = q.trim();
    if (!query) {
      setHits(null);
      return;
    }
    const timer = window.setTimeout(async () => {
      setSearching(true);
      try {
        setHits(await brain.search(query));
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Search failed.");
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => window.clearTimeout(timer);
  }, [q, searchNonce]);

  function deleted(r: BrainDeleteResult) {
    setHits((h) => (h ? h.filter((x) => x.title !== r.title) : h));
    setLastDeleted({ title: r.title, permanent: !!r.permanent });
    todayRes.reload().catch(() => undefined);
    deletedRes.reload(true).catch(() => undefined);
  }

  function restored() {
    setLastDeleted(null);
    setSearchNonce((n) => n + 1);
    todayRes.reload().catch(() => undefined);
    deletedRes.reload(true).catch(() => undefined);
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    const text = capture.trim();
    if (!text) return;
    try {
      const isUrl = /^https?:\/\/\S+$/.test(text);
      const result = await brain.capture(isUrl ? { url: text } : { text });
      setSaved(result.title);
      todayRes.reload().catch(() => undefined);
      setCapture("");
      window.setTimeout(() => setSaved(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Capture failed.");
    }
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">Your brain</p>
          <h1 className="page-head__title">Siris</h1>
        </div>
      </header>

      <Glass as="label" shape="pill" className="ask-bar" htmlFor="brain-search">
        <Search aria-hidden="true" />
        <input id="brain-search" className="ask-bar__input" placeholder="Search your notes" value={q} onChange={(e) => setQ(e.target.value)} />
      </Glass>

      {error && <div className="error-banner" role="alert" style={{ marginTop: 16 }}>{error}</div>}
      {lastDeleted && (
        <DeletedBar
          key={lastDeleted.title}
          title={lastDeleted.title}
          permanent={lastDeleted.permanent}
          onUndone={restored}
          onClose={() => setLastDeleted(null)}
        />
      )}

      {hits !== null ? (
        <>
          <h2 className="section-title">{searching ? "Searching…" : `${hits.length} note${hits.length === 1 ? "" : "s"}`}</h2>
          <div className="stack">
            {hits.map((hit) => (
              <Glass key={hit.path ?? hit.title} className="widget" style={{ minHeight: 0 }}>
                <div className="widget__head">
                  <BrainIcon style={{ color: "#a78bfa" }} aria-hidden="true" />
                  <span style={{ color: "var(--ink)", fontSize: 16 }}>{hit.title}</span>
                  {hit.type && <span className="chip" style={{ marginLeft: "auto" }}>{hit.type}</span>}
                </div>
                {(hit.excerpts ?? []).slice(0, 2).map((x, i) => (
                  <p key={i} className="muted" style={{ margin: 0 }}>{x}</p>
                ))}
                {hit.path && <p className="muted" style={{ margin: 0, fontSize: 12 }}>{hit.path}</p>}
                <div className="row note-actions">
                  <NoteConnections title={hit.title} />
                  <DeleteNoteButton title={hit.title} onDeleted={deleted} />
                </div>
              </Glass>
            ))}
          </div>
        </>
      ) : (
        <>
        <BrainMap />
        <div className="widget-grid" style={{ marginTop: 14 }}>
          <Glass as="form" className="widget" onSubmit={save} aria-label="Quick capture">
            <div className="widget__head">Quick capture</div>
            <textarea className="field" rows={3} placeholder="A thought, a link, a task…" value={capture} onChange={(e) => setCapture(e.target.value)} aria-label="Capture text" />
            <div className="row">
              {saved && (
                <span className="tone-good row" style={{ gap: 6, fontSize: 14 }}>
                  <Check size={16} aria-hidden="true" /> Saved “{saved}” to the inbox
                </span>
              )}
              <span className="spacer" />
              <Glass as="button" type="submit" variant="tint" shape="pill" interactive className="button button--small" disabled={!capture.trim()}>
                Capture
              </Glass>
            </div>
          </Glass>
          <Glass className="widget">
            <div className="widget__head">Learned today</div>
            {today === null ? (
              <div className="skeleton" style={{ height: 40 }} />
            ) : today.length === 0 ? (
              <p className="muted">Nothing new in the brain today.</p>
            ) : (
              <>
              <ul className="items">
                {learned.shown.map((item) => (
                  <li key={item.title} className="item">
                    <span className="item__dot" style={{ background: "#a78bfa" }} aria-hidden="true" />
                    <span className="item__text">
                      <div className="item__title">{item.title}</div>
                      <div className="item__subtitle">{item.action}</div>
                    </span>
                    <DeleteNoteButton title={item.title} compact onDeleted={deleted} />
                  </li>
                ))}
              </ul>
              {learned.toggle}
              </>
            )}
          </Glass>
        </div>
        <BrainInsights />
        <BrainManage onRestored={restored} />
        </>
      )}
    </>
  );
}
