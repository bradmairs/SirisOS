import { Link } from "react-router-dom";
import { CalendarClock, MoonStar, Sunrise, Target } from "lucide-react";
import type { HomeContext } from "../api/home";
import type { Hud } from "../api/types";
import { Glass } from "../components/Glass";

const at = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

/** The one thing Home leads with, for the part of the day (3.1). */
export function FocusCard({ ctx, events }: { ctx: HomeContext; events: Hud["next_events"] | undefined }) {
  const next = (events ?? []).find((e) => e.start && e.start.includes("T") && new Date(e.start).getTime() > Date.now() - 10 * 60_000);
  const soon = next && new Date(next.start).toDateString() === new Date().toDateString() ? next : null;

  if (ctx.phase === "morning") {
    return (
      <Glass as="section" className="widget widget--wide focus" aria-label="This morning">
        <header className="widget__head"><Sunrise aria-hidden="true" /><span>This morning</span></header>
        {ctx.top3.length > 0 ? (
          <>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>Your top 3, from last night:</p>
            <ol className="brief-top3">{ctx.top3.map((t) => <li key={t}>{t}</li>)}</ol>
          </>
        ) : soon ? <p style={{ margin: 0 }}>First up: <strong>{soon.summary}</strong> at {at(soon.start)}.</p>
          : <p className="muted" style={{ margin: 0 }}>Nothing set for today yet.</p>}
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <Link to="/brief" className="button button--small button--primary"><Sunrise size={14} aria-hidden="true" /> Today's brief</Link>
          <Link to="/tasks" className="button button--small">Tasks</Link>
        </div>
      </Glass>
    );
  }
  if (ctx.phase === "work") {
    return (
      <Glass as="section" className="widget widget--wide focus" aria-label="Next up">
        <header className="widget__head"><CalendarClock aria-hidden="true" /><span>Next up</span></header>
        {soon ? (
          <p style={{ margin: 0, fontSize: 17 }}><strong>{soon.summary}</strong> <span className="muted">at {at(soon.start)}</span></p>
        ) : <p className="muted" style={{ margin: 0 }}>No more meetings today.</p>}
        {ctx.top3.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 14 }}><Target size={13} aria-hidden="true" /> Top 3: {ctx.top3.join(" · ")}</p>}
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <Link to="/tasks" className="button button--small">Tasks</Link>
          <Link to="/engineering" className="button button--small">Engineering</Link>
        </div>
      </Glass>
    );
  }
  if (ctx.phase === "evening" || ctx.phase === "night") {
    return (
      <Glass as="section" className="widget widget--wide focus" aria-label="This evening">
        <header className="widget__head"><MoonStar aria-hidden="true" /><span>{ctx.wrapped_up ? "Tomorrow" : "Wrap up your day"}</span></header>
        {ctx.wrapped_up ? (
          ctx.tomorrow_top3.length > 0 ? <ol className="brief-top3">{ctx.tomorrow_top3.map((t) => <li key={t}>{t}</li>)}</ol>
            : <p className="muted" style={{ margin: 0 }}>Wrapped up. Nothing picked for tomorrow.</p>
        ) : (
          <>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>Two minutes: tick off what's done, log any CPD, pick tomorrow's top 3.</p>
            <div className="row"><Link to="/wrapup" className="button button--small button--primary"><MoonStar size={14} aria-hidden="true" /> Wrap up</Link></div>
          </>
        )}
      </Glass>
    );
  }
  return null;
}
