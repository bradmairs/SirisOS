import { useEffect, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  Award,
  Brain,
  CalendarDays,
  CloudSun,
  HeartPulse,
  House,
  ListChecks,
  Mail,
  Newspaper,
  RefreshCw,
  Sparkles,
  Sunrise,
  TriangleAlert,
  X,
} from "lucide-react";
import { brief as briefApi, type Brief, type BriefStory } from "../api/brief";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

const BRIEF_REFRESH_MS = 10 * 60_000;

/** The day's brief, shared by the morning overlay and the /brief screen. */
export function useBrief() {
  const { data, error, loading, reload } = useResource<Brief>("brief", (fresh) => briefApi.get(fresh), {
    refreshMs: BRIEF_REFRESH_MS,
    staleMs: 60_000,
  });
  return { brief: data ?? null, error: data ? null : error, refreshing: loading, reload: () => reload(true).catch(() => undefined) };
}

export function ago(iso: string | null, now = Date.now()): string {
  if (!iso) return "";
  const minutes = Math.round((now - new Date(iso).getTime()) / 60_000);
  if (!Number.isFinite(minutes)) return "";
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours} h ago` : `${Math.round(hours / 24)} d ago`;
}

function Card({ title, Icon, wide, delay = 0, children }: { title: string; Icon: typeof Sunrise; wide?: boolean; delay?: number; children: ReactNode }) {
  return (
    <Glass as="section" className={`widget ${wide ? "widget--wide" : ""}`} style={{ animationDelay: `${delay}ms` }} aria-label={title}>
      <header className="widget__head">
        <Icon aria-hidden="true" />
        <span>{title}</span>
      </header>
      {children}
    </Glass>
  );
}

function Row({ title, subtitle, tone = "neutral" }: { title: string; subtitle?: string | null; tone?: string }) {
  return (
    <li className="item">
      <span className={`item__dot dot-${tone}`} aria-hidden="true" />
      <span className="item__text">
        <span className="item__title" style={{ display: "block" }}>{title}</span>
        {subtitle && <span className="item__subtitle" style={{ display: "block" }}>{subtitle}</span>}
      </span>
    </li>
  );
}

function Story({ story }: { story: BriefStory }) {
  const meta = [story.source, ago(story.published)].filter(Boolean).join(" · ");
  return (
    <li>
      <a className="item brief-story" href={story.url} target="_blank" rel="noreferrer">
        <span className="item__text">
          <span className="brief-story__title">{story.title}</span>
          <span className="item__subtitle" style={{ display: "block" }}>
            {meta}
            {story.matches.length > 0 && <span className="brief-story__match"> · {story.matches.join(", ")}</span>}
          </span>
        </span>
        <ArrowUpRight size={15} className="brief-story__out" aria-hidden="true" />
      </a>
    </li>
  );
}

function Skeleton() {
  return (
    <div className="widget-grid" aria-busy="true" aria-label="Loading the brief">
      {[0, 1, 2, 3].map((i) => (
        <Glass key={i} className="widget">
          <div className="skeleton" style={{ height: 14, width: "40%" }} />
          <div className="skeleton" style={{ height: 30, width: "75%" }} />
          <div className="skeleton" style={{ height: 14, width: "90%" }} />
        </Glass>
      ))}
    </div>
  );
}

/**
 * The daily brief. `onClose` turns it into the morning overlay: a close
 * button up top and "Start my day" at the end, both of which dismiss it
 * for the rest of the day.
 */
export function BriefView({ onClose }: { onClose?: () => void }) {
  const { brief, error, refreshing, reload } = useBrief();
  const today = brief ? new Date(`${brief.date}T12:00:00`) : new Date();
  const wx = brief?.weather;
  const news = brief?.news.topics ?? [];

  return (
    <div className="brief-view">
      <header className="page-head">
        <div style={{ minWidth: 0 }}>
          <p className="page-head__eyebrow">
            <Sunrise size={16} className="brief-eyebrow-icon" aria-hidden="true" />
            Today's brief · {today.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}
          </p>
          <h1 className="page-head__title">{brief?.greeting ?? "Your day"}</h1>
        </div>
        <div className="row">
          <Glass as="button" shape="pill" interactive className="button button--icon" onClick={reload} aria-label="Refresh the brief">
            <RefreshCw className={refreshing ? "spin" : ""} aria-hidden="true" />
          </Glass>
          {onClose && (
            <Glass as="button" shape="pill" interactive className="button button--icon" onClick={onClose} aria-label="Close the brief">
              <X aria-hidden="true" />
            </Glass>
          )}
        </div>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}
      {!brief && !error && <Skeleton />}

      {brief && (
        <>
          <Glass as="section" className="brief-hero" aria-label="At a glance">
            <header className="widget__head">
              <Sparkles aria-hidden="true" />
              <span>At a glance</span>
            </header>
            <ul className="brief-hero__lines">
              {brief.headline.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </Glass>

          <h2 className="section-title">Your day</h2>
          <div className="widget-grid">
            {(wx?.today || wx?.now) && (
              <Card title="Weather" Icon={CloudSun}>
                <div className="row" style={{ alignItems: "baseline", gap: 12 }}>
                  {wx.now?.temperature_c != null && <span className="hud-big">{Math.round(wx.now.temperature_c)}°</span>}
                  <span className="hud-cond">{wx.now?.conditions ?? wx.today?.conditions}</span>
                </div>
                {wx.today?.conditions && wx.now && <p className="muted" style={{ margin: 0 }}>Today: {wx.today.conditions.toLowerCase()}</p>}
                {wx.today && (
                  <div className="metrics metrics--compact">
                    {wx.today.high_c != null && <Metric label="High" value={`${Math.round(wx.today.high_c)}°`} />}
                    {wx.today.low_c != null && <Metric label="Low" value={`${Math.round(wx.today.low_c)}°`} />}
                    {wx.today.rain_chance_percent != null && <Metric label="Rain" value={`${wx.today.rain_chance_percent}%`} />}
                  </div>
                )}
              </Card>
            )}

            <Card title="Schedule" Icon={CalendarDays} delay={40}>
              {brief.schedule.length ? (
                <ul className="items">
                  {brief.schedule.map((e, i) => (
                    <Row key={`${e.title}-${i}`} title={e.title} subtitle={[e.time, e.calendar, e.location].filter(Boolean).join(" · ")} />
                  ))}
                </ul>
              ) : (
                <p className="muted" style={{ margin: 0 }}>Nothing on the calendar today.</p>
              )}
            </Card>

            {(brief.tasks.length > 0 || brief.todo.length > 0) && (
              <Card title="Tasks" Icon={ListChecks} delay={80}>
                <ul className="items">
                  {brief.tasks.map((t, i) => (
                    <Row key={`${t.title}-${i}`} title={t.title} subtitle={[t.detail, t.source].filter(Boolean).join(" · ")} tone={t.tone} />
                  ))}
                  {brief.todo.map((t) => (
                    <Row key={`todo-${t}`} title={t} subtitle="To-do list" />
                  ))}
                </ul>
              </Card>
            )}

            {brief.email && (
              <Card title="Email" Icon={Mail} delay={120}>
                <p className="muted" style={{ margin: 0 }}>
                  {brief.email.unread ? `${brief.email.unread} unread since yesterday` : "No unread email."}
                </p>
                {brief.email.important.length > 0 && (
                  <ul className="items">
                    {brief.email.important.map((m, i) => (
                      <Row key={`${m.subject}-${i}`} title={m.subject} subtitle={m.from} tone="warning" />
                    ))}
                  </ul>
                )}
              </Card>
            )}

            {(brief.home.length > 0 || brief.health.length > 0) && (
              <Card title="Home & health" Icon={brief.home.length ? House : HeartPulse} delay={160}>
                <ul className="items">
                  {brief.home.map((h) => (
                    <Row key={h} title={h} />
                  ))}
                  {brief.health.map((h) => (
                    <Row key={h} title={h} tone="good" />
                  ))}
                </ul>
              </Card>
            )}

            {brief.apps_attention.length > 0 && (
              <Card title="Needs a look" Icon={TriangleAlert} delay={200}>
                <ul className="items">
                  {brief.apps_attention.map((a) => (
                    <Row key={a.name} title={a.name} subtitle={a.detail || a.state} tone={a.state === "down" ? "critical" : "warning"} />
                  ))}
                </ul>
              </Card>
            )}

            {brief.career && (brief.career.cpd.records > 0 || brief.career.next_steps.length > 0) && (
              <Card title="Career" Icon={Award} delay={220}>
                {brief.career.cpd.records > 0 && (
                  <p className="muted" style={{ margin: 0 }}>
                    {Math.round(brief.career.cpd.total)} of {brief.career.cpd.required} CPD hours in the last 3 years
                    {brief.career.cpd.expiring_90_days > 0 ? `; ${Math.round(brief.career.cpd.expiring_90_days)} h drop out within 90 days` : ""}.
                  </p>
                )}
                <ul className="items">
                  {brief.career.next_steps.map((s, i) => (
                    <Row key={`${s.title}-${i}`} title={s.title} subtitle={s.detail} tone={s.kind === "cpd" ? "warning" : "neutral"} />
                  ))}
                </ul>
                <Link to="/career" className="brief-link" onClick={onClose}>Open Career</Link>
              </Card>
            )}

            <Card title="Second Brain" Icon={Brain} delay={240}>
              <div className="metrics metrics--compact">
                <Metric label="In the inbox" value={String(brief.brain.inbox)} />
                <Metric label="Auto-linked" value={String(brief.brain.auto_linked)} />
                <Metric label="To check" value={String(brief.brain.unsure_links)} />
              </div>
              {brief.brain.highlights.length > 0 && (
                <ul className="items">
                  {brief.brain.highlights.map((h) => (
                    <Row key={h} title={h} />
                  ))}
                </ul>
              )}
              <Link to="/brain" className="brief-link" onClick={onClose}>Open Brain</Link>
            </Card>
          </div>

          <h2 className="section-title">
            <Newspaper size={14} className="brief-eyebrow-icon" aria-hidden="true" />
            News for you
          </h2>
          {news.length ? (
            <div className="widget-grid">
              {news.map((group, i) => (
                <Card key={group.topic} title={group.topic} Icon={Newspaper} delay={i * 40}>
                  <ul className="items">
                    {group.stories.map((s) => (
                      <Story key={s.url} story={s} />
                    ))}
                  </ul>
                </Card>
              ))}
            </div>
          ) : (
            <p className="muted" style={{ margin: "0 6px" }}>No news right now. The feeds may be unreachable; try refreshing later.</p>
          )}
          {brief.news.interests_from && (
            <p className="muted brief-footnote">
              Picked from your {brief.news.interests_from.startsWith("default") ? brief.news.interests_from : `“${brief.news.interests_from}” note`} and the interests linked from your own note.
            </p>
          )}

          {brief.unavailable.length > 0 && (
            <p className="muted brief-footnote">Couldn't reach: {brief.unavailable.join(", ")}. Those sections are left out.</p>
          )}
          <p className="muted brief-footnote">
            Updated {new Date(brief.generated_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
          </p>

          {onClose && (
            <div className="brief-done">
              <Glass as="button" variant="tint" shape="pill" interactive className="button" onClick={onClose}>
                <Sunrise aria-hidden="true" /> Start my day
              </Glass>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="metric__value">{value}</div>
      <div className="metric__label">{label}</div>
    </div>
  );
}

/** /brief: the brief any time of day, without dismissing anything. */
export function BriefScreen() {
  return <BriefView />;
}

/** The morning overlay: full screen over the shell until closed. */
export function BriefOverlay({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.classList.add("no-scroll");
    ref.current?.focus();
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.classList.remove("no-scroll");
    };
  }, [onClose]);
  return (
    <div ref={ref} className="brief-overlay" role="dialog" aria-modal="true" aria-label="Today's brief" tabIndex={-1}>
      <div className="brief-overlay__inner">
        <BriefView onClose={onClose} />
      </div>
    </div>
  );
}
