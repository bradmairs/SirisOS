import { useEffect, useRef, useState } from "react";
import { Maximize2, Minimize2, RotateCw } from "lucide-react";
import { brain } from "../api/hub";
import { Glass } from "../components/Glass";

/**
 * Siris' living mind map (Siris-Second-Brain tools/mindmap.html),
 * drawn fresh from the vault by SirisAI and proxied through SirisOS. It runs in
 * a sandboxed iframe without same-origin access, so it can't read the session.
 */
export function BrainMap() {
  const [html, setHtml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [version, setVersion] = useState(0);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [gone, setGone] = useState<{ title: string; error?: string } | null>(null);

  // 8.3: the map's "Delete note" asks here (it has no key of its own). Only a message from our own map counts; it's
  // confirmed, deleted the way Siris' Manage does (restorable), and the map is drawn again without it.
  useEffect(() => {
    const onMessage = async (e: MessageEvent) => {
      if (!frameRef.current || e.source !== frameRef.current.contentWindow) return;
      const data = e.data as { type?: string; title?: unknown };
      if (data?.type !== "siris-map:delete" || typeof data.title !== "string" || !data.title.trim()) return;
      const title = data.title.slice(0, 200);
      if (!window.confirm(`Delete "${title}" from Siris? It goes to Siris' deleted notes, and you can undo it.`)) return;
      try {
        await brain.remove(title);
        setGone({ title });
        setVersion((v) => v + 1);
      } catch (err) {
        setGone({ title, error: err instanceof Error ? err.message : String(err) });
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);
  const undo = async () => {
    if (!gone) return;
    try { await brain.restore(gone.title); setGone(null); setVersion((v) => v + 1); }
    catch (err) { setGone({ ...gone, error: err instanceof Error ? err.message : String(err) }); }
  };
  const note = gone && (
    <p className={gone.error ? "tone-critical brain-map__note" : "muted brain-map__note"} role={gone.error ? "alert" : "status"}>
      {gone.error ? `Couldn't delete "${gone.title}": ${gone.error}` : <>Deleted "{gone.title}". <button type="button" className="icon-link" onClick={undo}>Undo</button></>}
    </p>
  );

  useEffect(() => {
    let live = true;
    setHtml(null);
    setError(null);
    brain
      .map()
      .then((page) => live && setHtml(page))
      .catch((err) => live && setError(err instanceof Error ? err.message : "The mind map didn't load."));
    return () => {
      live = false;
    };
  }, [version]);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setExpanded(false);
    window.addEventListener("keydown", onKey);
    document.body.classList.add("no-scroll");
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.classList.remove("no-scroll");
    };
  }, [expanded]);

  const frame =
    html === null ? (
      error ? (
        <div className="brain-map__empty">
          <p className="muted">{error}</p>
        </div>
      ) : (
        <div className="skeleton brain-map__frame" />
      )
    ) : (
      <iframe ref={frameRef} className="brain-map__frame" title="Siris mind map" srcDoc={html} sandbox="allow-scripts allow-popups" />
    );

  const controls = (
    <>
      <button type="button" className="icon-link" onClick={() => setVersion((v) => v + 1)} aria-label="Redraw the mind map" title="Redraw from the vault">
        <RotateCw size={17} aria-hidden="true" />
      </button>
      <button
        type="button"
        className="icon-link"
        onClick={() => setExpanded((v) => !v)}
        aria-label={expanded ? "Close full screen" : "Open the mind map full screen"}
        title={expanded ? "Close full screen" : "Full screen"}
      >
        {expanded ? <Minimize2 size={17} aria-hidden="true" /> : <Maximize2 size={17} aria-hidden="true" />}
      </button>
    </>
  );

  if (expanded) {
    return (
      <div className="brain-map--full" role="dialog" aria-modal="true" aria-label="Mind map">
        <Glass variant="strong" shape="pill" className="brain-map__bar">
          <span className="brain-map__title">Mind map</span>
          <span className="spacer" />
          {controls}
        </Glass>
        {note}
        {frame}
      </div>
    );
  }

  return (
    <Glass className="widget brain-map" aria-label="Mind map">
      <div className="widget__head">
        Mind map
        <span className="spacer" />
        {controls}
      </div>
      {note}
      {frame}
    </Glass>
  );
}
