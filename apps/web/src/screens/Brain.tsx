import { useEffect, useState, type FormEvent } from "react";
import { Brain as BrainIcon, Check, Search } from "lucide-react";
import { brain } from "../api/hub";
import { useResource } from "../api/resource";
import type { BrainHit } from "../api/types";
import { Glass } from "../components/Glass";
import { BrainInsights } from "./BrainInsights";
import { BrainMap } from "./BrainMap";
import { NoteConnections } from "./NoteConnections";

export function Brain() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<BrainHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const todayRes = useResource("brain:today", () => brain.today(), { refreshMs: 120_000 });
  const today = todayRes.data?.items ?? null;
  const [capture, setCapture] = useState("");
  const [saved, setSaved] = useState<string | null>(null);

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
  }, [q]);

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
          <p className="page-head__eyebrow">Second Brain</p>
          <h1 className="page-head__title">Brain</h1>
        </div>
      </header>

      <Glass as="label" shape="pill" className="ask-bar" htmlFor="brain-search">
        <Search aria-hidden="true" />
        <input id="brain-search" className="ask-bar__input" placeholder="Search your notes" value={q} onChange={(e) => setQ(e.target.value)} />
      </Glass>

      {error && <div className="error-banner" role="alert" style={{ marginTop: 16 }}>{error}</div>}

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
                <NoteConnections title={hit.title} />
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
              <ul className="items">
                {today.map((item) => (
                  <li key={item.title} className="item">
                    <span className="item__dot" style={{ background: "#a78bfa" }} aria-hidden="true" />
                    <span className="item__text">
                      <div className="item__title">{item.title}</div>
                      <div className="item__subtitle">{item.action}</div>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Glass>
        </div>
        <BrainInsights />
        </>
      )}
    </>
  );
}
