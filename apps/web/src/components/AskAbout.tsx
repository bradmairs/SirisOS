import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Sparkles, X } from "lucide-react";
import { handOff, pageContext } from "../api/pageContext";
import { NAV } from "./Sidebar";
import { Glass } from "./Glass";

const HIDDEN = ["/assistant", "/gym/workout", "/terminal", "/act"];

function titleFor(pathname: string): string {
  const top = `/${pathname.split("/")[1]}`;
  return NAV.find((n) => n.to === top)?.label ?? (top === "/" ? "Home" : top.slice(1));
}

/** 7.5: ask Siris about the page you're on. The page's own summary (usePageContext) goes with the question. */
export function AskAbout({ variant }: { variant: "fab" | "topbar" }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => { if (open) input.current?.focus(); }, [open]);
  if (HIDDEN.some((h) => pathname === h || pathname.startsWith(`${h}/`))) return null;
  const ctx = pageContext();
  const title = ctx?.title ?? titleFor(pathname);
  const ask = () => {
    if (!q.trim()) return;
    handOff(ctx ?? { title, summary: "", path: pathname });
    setOpen(false);
    navigate(`/assistant?q=${encodeURIComponent(q.trim())}&about=1`);
    setQ("");
  };
  return (
    <>
      {variant === "fab" ? (
        <Glass as="button" shape="pill" interactive className="ask-fab" onClick={() => setOpen(true)} aria-label={`Ask Siris about ${title}`}>
          <Sparkles size={17} aria-hidden="true" /><span>Ask about this</span>
        </Glass>
      ) : (
        <button type="button" className="icon-link topbar__ask" onClick={() => setOpen(true)} aria-label={`Ask Siris about ${title}`}>
          <Sparkles size={19} aria-hidden="true" />
        </button>
      )}
      {open && (
        <div className="ask-about" role="dialog" aria-label={`Ask Siris about ${title}`}>
          <div className="ask-about__scrim" onClick={() => setOpen(false)} />
          <Glass as="form" className="ask-about__card" onSubmit={(e: React.FormEvent) => { e.preventDefault(); ask(); }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <strong><Sparkles size={15} aria-hidden="true" /> Ask about {title}</strong>
              <button type="button" className="icon-link" onClick={() => setOpen(false)} aria-label="Close"><X size={18} aria-hidden="true" /></button>
            </div>
            <input ref={input} className="field" placeholder={ctx ? "What should I focus on here?" : `A question about ${title}`} aria-label="Your question"
              value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }} />
            <p className="muted" style={{ margin: 0, fontSize: 12 }}>{ctx ? "What's on this page goes with your question." : "Siris knows which page you asked from."}</p>
            <button type="submit" className="button button--primary" disabled={!q.trim()} style={{ alignSelf: "flex-end" }}>Ask</button>
          </Glass>
        </div>
      )}
    </>
  );
}
