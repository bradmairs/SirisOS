import { useState } from "react";
import { Link } from "react-router-dom";
import { CalendarClock, Check, Circle, CloudRain, House, MapPin, MoonStar, Sun, Sunrise, Target } from "lucide-react";
import type { DayEvent, DayWeather, HomeContext } from "../api/home";
import { tasks, type TaskItem } from "../api/tasks";
import type { Hud } from "../api/types";
import { Glass } from "../components/Glass";
import { useTasks } from "./Tasks";

const at = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
const dayOf = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const timed = (e: DayEvent) => !e.all_day && e.start.includes("T");
const WELCOME_MINUTES = 45;

/** Today's and tomorrow's events: the context's, or the HUD's next few until it answers. */
function eventsOf(ctx: HomeContext, hud: Hud["next_events"] | undefined): DayEvent[] {
  if (ctx.events) return ctx.events;
  return (hud ?? []).map((e) => ({ title: e.summary, start: e.start, all_day: !e.start.includes("T"), location: null }));
}

/** When to head off for an event with a place: its start less the leave margin. */
function leaveBy(e: DayEvent, minutes: number | undefined): string | null {
  if (!e.location || !timed(e) || !minutes) return null;
  return at(new Date(new Date(e.start).getTime() - minutes * 60_000).toISOString());
}

function until(iso: string, now: Date): string {
  const mins = Math.round((new Date(iso).getTime() - now.getTime()) / 60_000);
  if (mins <= 0) return "now";
  if (mins < 60) return `in ${mins} min`;
  return `at ${at(iso)}`;
}

function Weather({ w, label }: { w: DayWeather | null | undefined; label: string }) {
  if (!w) return null;
  const rain = w.rain_chance_percent ?? 0;
  const wet = rain >= 50;
  return (
    <p className={wet ? "focus__rain" : "muted"} style={{ margin: 0, fontSize: 14 }}>
      {wet ? <CloudRain size={14} aria-hidden="true" /> : <Sun size={14} aria-hidden="true" />}{" "}
      {label}: {w.high_c != null ? `${Math.round(w.high_c)}°` : ""}{w.conditions ? `, ${w.conditions}` : ""}{rain ? `, ${Math.round(rain)}% chance of rain` : ""}
      {wet ? ". Take an umbrella." : ""}
    </p>
  );
}

function EventLine({ e, leave, prefix = "" }: { e: DayEvent; leave?: number; prefix?: string }) {
  const go = leaveBy(e, leave);
  return (
    <p style={{ margin: 0 }}>
      {prefix}<strong>{e.title}</strong> {timed(e) ? <>at {at(e.start)}</> : <span className="muted">all day</span>}
      {e.location && <span className="muted"> · <MapPin size={12} aria-hidden="true" /> {e.location}</span>}
      {go && <span className="focus__leave"> · leave by {go}</span>}
    </p>
  );
}

/** Your top 3, ticked off here when they're on your task list. */
function Top3({ items }: { items: string[] }) {
  const res = useTasks();
  const [done, setDone] = useState<string[]>([]);
  const open: TaskItem[] = res.data ? Object.values(res.data.groups).flat() : [];
  const find = (title: string) => open.find((t) => t.title.trim().toLowerCase() === title.trim().toLowerCase());
  return (
    <ul className="items focus__top3" aria-label="Top 3">
      {items.map((title) => {
        const task = find(title);
        const ticked = done.includes(title);
        return (
          <li key={title} className={`item task${ticked ? " task--done" : ""}`}>
            {task || ticked ? (
              <button type="button" className="task__tick" disabled={ticked} aria-label={`Done: ${title}`}
                onClick={() => task && tasks.done(task).then(() => { setDone((d) => [...d, title]); res.reload(true).catch(() => undefined); }).catch(() => undefined)}>
                {ticked ? <Check size={18} aria-hidden="true" /> : <Circle size={18} aria-hidden="true" />}
              </button>
            ) : <Target size={16} aria-hidden="true" className="muted" />}
            <span className="item__text"><div className="item__title">{title}</div></span>
          </li>
        );
      })}
    </ul>
  );
}

/** The one thing Home leads with, for the part of the day (3.1, 4.9). */
export function FocusCard({ ctx, events: hudEvents, parcels = 0, inbox = 0, now = new Date() }: {
  ctx: HomeContext;
  events: Hud["next_events"] | undefined;
  /** Parcels on their way or delivered, and open inbox items: for the welcome home. */
  parcels?: number;
  inbox?: number;
  now?: Date;
}) {
  const events = eventsOf(ctx, hudEvents);
  const today = dayOf(now);
  const tomorrow = dayOf(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1));
  const todays = events.filter((e) => e.start.slice(0, 10) === today);
  const upcoming = todays.filter((e) => timed(e) && new Date(e.start).getTime() > now.getTime() - 10 * 60_000);
  const firstTomorrow = events.find((e) => e.start.slice(0, 10) === tomorrow && timed(e)) ?? events.find((e) => e.start.slice(0, 10) === tomorrow);

  if (ctx.phase === "morning") {
    const first = upcoming[0];
    return (
      <Glass as="section" className="widget widget--wide focus" aria-label="This morning">
        <header className="widget__head"><Sunrise aria-hidden="true" /><span>This morning</span></header>
        {first ? <EventLine e={first} leave={ctx.leave_minutes} prefix="First up: " /> : <p className="muted" style={{ margin: 0 }}>Nothing on the calendar this morning.</p>}
        <Weather w={ctx.weather_today} label="Today" />
        {ctx.top3.length > 0 && (
          <>
            <p className="muted" style={{ margin: 0, fontSize: 14 }}>Your top 3, from last night:</p>
            <Top3 items={ctx.top3} />
          </>
        )}
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <Link to="/brief" className="button button--small button--primary"><Sunrise size={14} aria-hidden="true" /> Today's brief</Link>
          <Link to="/tasks" className="button button--small">Tasks</Link>
        </div>
      </Glass>
    );
  }
  if (ctx.phase === "work") {
    const next = upcoming[0];
    return (
      <Glass as="section" className="widget widget--wide focus" aria-label="Next up">
        <header className="widget__head"><CalendarClock aria-hidden="true" /><span>Next up</span></header>
        {next ? (
          <p style={{ margin: 0, fontSize: 17 }}><strong>{next.title}</strong> <span className="focus__when">{until(next.start, now)}</span>
            {next.location && <span className="muted" style={{ fontSize: 14 }}> · {next.location}</span>}</p>
        ) : <p className="muted" style={{ margin: 0 }}>No more meetings today.</p>}
        {ctx.top3.length > 0 && <Top3 items={ctx.top3} />}
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <Link to="/tasks" className="button button--small">Tasks</Link>
          <Link to="/engineering" className="button button--small">Engineering</Link>
        </div>
      </Glass>
    );
  }
  if (ctx.phase === "weekend") {
    return (
      <Glass as="section" className="widget widget--wide focus" aria-label="Today">
        <header className="widget__head"><Sun aria-hidden="true" /><span>Today</span></header>
        {/* What's still to come: all-day plans, then the rest by time. */}
        {(() => {
          const left = todays.filter((e) => !timed(e) || upcoming.includes(e));
          return left.length > 0 ? left.slice(0, 4).map((e) => <EventLine key={`${e.title}-${e.start}`} e={e} leave={ctx.leave_minutes} />)
            : <p className="muted" style={{ margin: 0 }}>{todays.length ? "Nothing else planned today." : "Nothing planned. A free day."}</p>;
        })()}
        <Weather w={ctx.weather_today} label="Outside today" />
      </Glass>
    );
  }
  if (ctx.phase === "evening") {
    const since = ctx.home && ctx.home_since ? (now.getTime() - new Date(ctx.home_since).getTime()) / 60_000 : Infinity;
    const welcome = since >= 0 && since <= WELCOME_MINUTES;
    return (
      <Glass as="section" className="widget widget--wide focus" aria-label="This evening">
        {welcome && (
          <div className="focus__welcome" role="status">
            <House size={15} aria-hidden="true" /> <strong>Welcome home.</strong>{" "}
            <span className="muted">
              {[parcels ? `${parcels} parcel${parcels === 1 ? "" : "s"} on the way or delivered` : "", inbox ? `${inbox} thing${inbox === 1 ? "" : "s"} in your inbox` : ""]
                .filter(Boolean).join(" · ") || "Nothing new while you were out."}
            </span>
          </div>
        )}
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
        {upcoming.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 14 }}>Tonight: {upcoming.slice(0, 2).map((e) => `${e.title} at ${at(e.start)}`).join(" · ")}</p>}
      </Glass>
    );
  }
  // Wind down and night: tomorrow, quietly.
  return (
    <Glass as="section" className="widget widget--wide focus focus--quiet" aria-label="Tomorrow">
      <header className="widget__head"><MoonStar aria-hidden="true" /><span>Tomorrow</span></header>
      {ctx.phase === "night" && <p className="focus__clock" aria-label="Now">{now.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}</p>}
      {firstTomorrow ? <EventLine e={firstTomorrow} leave={ctx.leave_minutes} prefix="First: " /> : <p className="muted" style={{ margin: 0 }}>Nothing on first thing.</p>}
      {ctx.phase === "winddown" && (
        <>
          <Weather w={ctx.weather_tomorrow} label="Tomorrow" />
          {ctx.tomorrow_top3.length > 0 ? <ol className="brief-top3">{ctx.tomorrow_top3.map((t) => <li key={t}>{t}</li>)}</ol>
            : !ctx.wrapped_up && <Link to="/wrapup" className="button button--small"><MoonStar size={14} aria-hidden="true" /> Wrap up and pick tomorrow's top 3</Link>}
        </>
      )}
    </Glass>
  );
}
