import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertTriangle, Award, CalendarDays, ChevronLeft, ChevronRight, CloudRain, Flag, FolderKanban, GraduationCap } from "lucide-react";
import { useResource } from "../api/resource";
import { shift, week as weekApi, type Week, type WeekDay, type WeekEvent } from "../api/week";
import { Glass } from "../components/Glass";

function dayLabel(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });
}

function time(iso: string | null) {
  if (!iso || iso.length <= 10) return "";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

const hours = (h: number) => `${Number.isInteger(h) ? h : h.toFixed(1)} h`;

/** This week: every day's events and forecast, what's due, and the week's CPD. */
export function WeekScreen() {
  const [params, setParams] = useSearchParams();
  const start = params.get("start") ?? undefined;
  const { data, error, loading } = useResource<Week>(`week:${start ?? "this"}`, () => weekApi.get(start), { staleMs: 60_000, persist: !start });
  useEffect(() => {
    document.title = "This week · SirisOS";
  }, []);
  const go = (by: number) => data && setParams({ start: shift(data.start, by) });

  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{data ? `${dayLabel(data.start)} – ${dayLabel(shift(data.end, -1))}` : "Week"}</p>
          <h1 className="page-head__title">{!start || (data && data.start <= data.today && data.today < data.end) ? "This week" : "Week"}</h1>
        </div>
        <div className="row">
          <Glass as="button" shape="pill" interactive className="button button--icon" onClick={() => go(-7)} aria-label="Previous week" disabled={!data}>
            <ChevronLeft aria-hidden="true" />
          </Glass>
          {start && (
            <Glass as="button" shape="pill" interactive className="button button--small" onClick={() => setParams({})}>Today</Glass>
          )}
          <Glass as="button" shape="pill" interactive className="button button--icon" onClick={() => go(7)} aria-label="Next week" disabled={!data}>
            <ChevronRight aria-hidden="true" />
          </Glass>
        </div>
      </header>

      {error && !data && <div className="error-banner" role="alert">{error}</div>}
      {!data && loading && <div className="skeleton" style={{ height: 240, marginTop: 16 }} />}
      {data && <WeekBody week={data} />}
    </>
  );
}

function WeekBody({ week }: { week: Week }) {
  const events = week.days.reduce((n, d) => n + d.events.length, 0);
  const due = week.days.reduce((n, d) => n + d.due.length, 0);
  return (
    <>
      {week.guest_mode && <p className="guest-banner" role="status">Guest mode is on: your calendar is hidden.</p>}
      {week.unavailable.includes("calendar") && !week.guest_mode && (
        <p className="muted" role="status" style={{ margin: "12px 6px 0" }}>The calendar isn't available right now (SirisAI 1.21 or later reads it).</p>
      )}
      <div className="metrics week-summary" aria-label="The week at a glance">
        <div><div className="metric__value">{events}</div><div className="metric__label">Events</div></div>
        <div><div className={`metric__value ${due ? "tone-warning" : ""}`}>{due}</div><div className="metric__label">Due</div></div>
        <div><div className="metric__value">{hours(week.cpd.logged + week.cpd.planned)}</div><div className="metric__label">CPD</div></div>
      </div>

      {week.overdue.length > 0 && (
        <Glass as="section" className="widget" style={{ minHeight: 0, marginTop: 16 }} aria-label="Overdue">
          <header className="widget__head"><AlertTriangle aria-hidden="true" /><span>Overdue</span></header>
          <ul className="items">
            {week.overdue.map((t, i) => (
              <li key={i} className="item">
                <span className="item__dot dot-critical" aria-hidden="true" />
                <span className="item__text"><div className="item__title">{t.title}</div><div className="item__subtitle">{t.detail}</div></span>
              </li>
            ))}
          </ul>
        </Glass>
      )}

      <div className="week-days">
        {week.days.map((day) => <DayCard key={day.date} day={day} today={day.date === week.today} past={day.date < week.today} />)}
      </div>
      {(week.cpd.logged > 0 || week.cpd.planned > 0) && (
        <p className="muted" style={{ margin: "14px 6px 0", fontSize: 13 }}>
          <Award size={13} aria-hidden="true" style={{ verticalAlign: "-2px" }} /> CPD this week: {hours(week.cpd.logged)} in your Engineers Australia import
          {week.cpd.planned > 0 && `, ${hours(week.cpd.planned)} on the calendar`}. <Link to="/career?view=cpd">CPD</Link>
        </p>
      )}
    </>
  );
}

function DayCard({ day, today, past }: { day: WeekDay; today: boolean; past: boolean }) {
  const f = day.forecast;
  return (
    <Glass as="section" className={`widget week-day ${today ? "week-day--today" : ""} ${past ? "week-day--past" : ""}`} aria-label={dayLabel(day.date)}>
      <header className="widget__head">
        <CalendarDays aria-hidden="true" />
        <span>{today ? `Today · ${dayLabel(day.date)}` : dayLabel(day.date)}</span>
        {f && (
          <span className="week-day__weather" title={f.conditions ?? ""}>
            {f.rain_chance_percent != null && f.rain_chance_percent >= 40 && <CloudRain size={13} aria-hidden="true" />}
            {f.high_c != null && `${Math.round(f.high_c)}°`}{f.low_c != null && <span className="muted"> / {Math.round(f.low_c)}°</span>}
            {f.rain_chance_percent != null && f.rain_chance_percent >= 40 && <span className="muted"> · {Math.round(f.rain_chance_percent)}%</span>}
          </span>
        )}
      </header>
      {day.events.length === 0 && day.due.length === 0 ? (
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>Nothing on.</p>
      ) : (
        <ul className="items">
          {day.due.map((d, i) => (
            <li key={`due-${i}`} className="item">
              {d.kind === "goal" ? <Flag size={14} className="tone-warning" aria-hidden="true" /> : <FolderKanban size={14} className="tone-warning" aria-hidden="true" />}
              <span className="item__text"><div className="item__title">{d.title}</div><div className="item__subtitle">Due · {d.source}</div></span>
            </li>
          ))}
          {day.events.map((e, i) => <EventRow key={`${e.title}-${i}`} event={e} />)}
        </ul>
      )}
      {day.cpd_hours > 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{hours(day.cpd_hours)} CPD logged</p>}
    </Glass>
  );
}

function EventRow({ event: e }: { event: WeekEvent }) {
  const when = e.all_day ? "All day" : [time(e.start), time(e.end)].filter(Boolean).join(" – ");
  return (
    <li className="item">
      <span className="item__dot" aria-hidden="true" />
      <span className="item__text">
        <div className="item__title">{e.title}</div>
        <div className="item__subtitle">
          {[when, e.location, e.calendar].filter(Boolean).join(" · ")}
          {e.cpd && <> · <GraduationCap size={12} aria-hidden="true" style={{ verticalAlign: "-2px" }} /> CPD {hours(e.cpd.hours)}</>}
        </div>
      </span>
    </li>
  );
}
