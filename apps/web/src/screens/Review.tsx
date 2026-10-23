import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarRange, Check, Compass, Hourglass, TrendingUp } from "lucide-react";
import { useResource } from "../api/resource";
import { review, type WeeklyReview } from "../api/review";
import { Glass } from "../components/Glass";

const dayName = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });

function nextMonday(monday: string): string {
  const d = new Date(`${monday}T12:00:00`);
  d.setDate(d.getDate() + 7);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function Metric({ value, label }: { value: string | number | null; label: string }) {
  if (value === null || value === undefined) return null;
  return <div><div className="metric__value">{value}</div><div className="metric__label">{label}</div></div>;
}

/** Sunday's look back and ahead (3.5). */
export function ReviewScreen() {
  const res = useResource<WeeklyReview>("review:week", () => review.get(), { staleMs: 60_000 });
  const data = res.data ?? null;
  const [focus, setFocus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Weekly review · SirisOS";
  }, []);
  useEffect(() => {
    if (data && focus === null) setFocus(data.saved?.focus ?? "");
  }, [data, focus]);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const r = await review.save(focus ?? "");
      setNote(r.saved_as ? `Saved to Siris as “${r.saved_as}”. It's on This week from Monday.` : "Saved. It's on This week from Monday.");
      await res.reload(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save.");
    } finally {
      setBusy(false);
    }
  }

  const n = data?.numbers;
  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{data ? `Week of ${dayName(data.week_of)}` : "This week"}</p>
          <h1 className="page-head__title">Weekly review</h1>
        </div>
      </header>
      <div className="stack" style={{ marginTop: 16 }}>
        {!data && !res.error && <div className="skeleton" style={{ height: 200 }} aria-label="Loading" />}
        {!data && res.error && <p className="tone-critical">{res.error}</p>}
        {data && n && (
          <>
            <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="The week">
              <header className="widget__head"><TrendingUp aria-hidden="true" /><span>The week</span></header>
              <div className="metrics">
                <Metric value={n.tasks_done} label="Tasks done" />
                <Metric value={n.notes} label={n.notes_before !== null ? `Notes in Siris · ${n.notes_before} the week before` : "Notes in Siris"} />
                <Metric value={n.cpd_hours ? `${n.cpd_hours} h` : 0} label="CPD" />
                <Metric value={n.runs !== null ? (n.runs ? `${n.runs} · ${n.run_km} km` : 0) : null} label="Runs" />
                <Metric value={n.exercise_minutes !== null ? `${n.exercise_minutes} min` : null} label="Exercise" />
                <Metric value={n.meetings} label="Meetings" />
                <Metric value={n.wrapped_up} label="Days wrapped up" />
              </div>
              {data.done.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 14 }}>Done: {data.done.join(" · ")}</p>}
            </Glass>

            {data.quiet.length > 0 && (
              <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Going quiet">
                <header className="widget__head"><Hourglass aria-hidden="true" /><span>Going quiet</span></header>
                <ul className="items">
                  {data.quiet.map((p) => (
                    <li key={p.title} className="item">
                      <span className="item__text">
                        <Link to={`/projects/${encodeURIComponent(p.title)}`} className="item__title" style={{ color: "inherit" }}>{p.title}</Link>
                        <div className="item__subtitle">Untouched for {p.days_idle} days</div>
                      </span>
                    </li>
                  ))}
                </ul>
              </Glass>
            )}

            <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Next week">
              <header className="widget__head"><CalendarRange aria-hidden="true" /><span>Next week</span></header>
              {data.next_week.meetings !== null && <p className="muted" style={{ margin: 0, fontSize: 14 }}>{data.next_week.meetings} meetings.</p>}
              {data.next_week.busy_days.length === 0 && data.next_week.tasks.length === 0 && data.next_week.deadlines.length === 0 && (
                <p className="muted" style={{ margin: 0 }}>Nothing crunchy on the way.</p>
              )}
              <ul className="items">
                {data.next_week.busy_days.map((d) => (
                  <li key={d.date} className="item task">
                    <span className="item__dot dot-warning" aria-hidden="true" />
                    <span className="item__text">
                      <div className="item__title">{dayName(d.date)}: {d.meetings} meetings</div>
                      {d.clashes.length > 0 && <div className="item__subtitle tone-warning">Clash: {d.clashes.join("; ")}</div>}
                    </span>
                  </li>
                ))}
                {data.next_week.deadlines.map((d) => (
                  <li key={d.title} className="item task">
                    <span className="item__dot dot-critical" aria-hidden="true" />
                    <span className="item__text"><div className="item__title">{d.title}</div><div className="item__subtitle">Project due in {d.days_left} days</div></span>
                  </li>
                ))}
                {data.next_week.tasks.map((t) => (
                  <li key={t.id} className="item task">
                    <span className="item__dot" aria-hidden="true" />
                    <span className="item__text"><div className="item__title">{t.title}</div><div className="item__subtitle">Due {t.due ? dayName(t.due) : ""}</div></span>
                  </li>
                ))}
              </ul>
              <Link to={`/week?start=${nextMonday(data.week_of)}`} className="show-more">Open next week</Link>
            </Glass>

            <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="What matters next week">
              <header className="widget__head"><Compass aria-hidden="true" /><span>What matters next week</span></header>
              <textarea className="field" rows={4} value={focus ?? ""} onChange={(e) => setFocus(e.target.value)} aria-label="Your note for next week"
                placeholder="The one or two things that would make next week a good one." />
              <button type="button" className="button button--primary" disabled={busy} onClick={save}>{busy ? "Saving…" : data.saved ? "Update" : "Save"}</button>
              {note && <p className="tone-good suggest__done" role="status" style={{ margin: 0 }}><Check size={14} aria-hidden="true" /> {note}</p>}
              {error && <p className="tone-critical" role="alert" style={{ margin: 0 }}>{error}</p>}
            </Glass>
          </>
        )}
      </div>
    </>
  );
}
