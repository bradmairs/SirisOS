import { useEffect } from "react";
import { Activity, HardDrive, RefreshCw } from "lucide-react";
import { useResource } from "../api/resource";
import { systemStatus, type AppHealth } from "../api/status";
import { fitness } from "../api/fitness";
import { Glass } from "../components/Glass";
import { AccessCheckCard } from "./AccessCheck";
import { BackupsCard } from "./BackupsCard";
import { hueFor, iconFor } from "../components/icons";

function when(epoch: number) {
  const d = new Date(epoch * 1000);
  const today = new Date().toDateString() === d.toDateString();
  return (today ? "" : d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" }) + " ") +
    d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

const pct = (v: number | null) => (v == null ? "–" : `${v % 1 === 0 ? v : v.toFixed(1)}%`);

/** Each app's health now and over the last day and week. */
export function StatusScreen() {
  const { data, error, loading, reload } = useResource("hub:status", () => systemStatus.get(), { refreshMs: 60_000, persist: true });
  useEffect(() => {
    document.title = "System status · SirisOS";
  }, []);
  const apps = data?.apps ?? [];
  const down = apps.filter((a) => a.status.state === "down").length;
  const degraded = apps.filter((a) => a.status.state === "degraded").length;

  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{data ? (down ? `${down} down` : degraded ? `${degraded} need${degraded === 1 ? "s" : ""} a look` : "Everything's up") : "Checking…"}</p>
          <h1 className="page-head__title">System status</h1>
        </div>
        <Glass as="button" shape="pill" interactive className="button button--icon" onClick={() => reload(true).catch(() => undefined)} aria-label="Check again">
          <RefreshCw className={loading ? "spin" : ""} aria-hidden="true" />
        </Glass>
      </header>
      {error && !data && <div className="error-banner" role="alert">{error}</div>}
      {data && apps.length === 0 && <p className="muted">No apps are set up yet.</p>}
      <div className="stack" style={{ marginTop: 16 }}>
        <AccessCheckCard />
        <UpkeepCard />
        <BackupsCard />
        {apps.map((a) => <AppCard key={a.id} app={a} />)}
      </div>
      {data && (
        <p className="muted" style={{ margin: "14px 6px 0", fontSize: 13 }}>
          Checked every {data.sample_every_minutes} minutes, and whenever SirisOS is open. Seven days are kept.
        </p>
      )}
    </>
  );
}

function AppCard({ app }: { app: AppHealth }) {
  const Icon = iconFor(app.icon);
  const state = app.status.state;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label={app.name}>
      <header className="widget__head">
        <Icon style={{ color: hueFor(app.id) }} aria-hidden="true" />
        <span>{app.name}</span>
        <span className={`chip status-chip status-chip--${state}`} style={{ marginLeft: "auto" }}>{state === "ok" ? "Up" : state === "degraded" ? "Degraded" : state === "down" ? "Down" : "Not set up"}</span>
      </header>
      {state !== "ok" && app.status.detail && <p className="muted" style={{ margin: 0, fontSize: 14 }}>{app.status.detail}</p>}
      <div className="metrics">
        <div><div className="metric__value">{pct(app.uptime_24h)}</div><div className="metric__label">Up, 24 h</div></div>
        <div><div className="metric__value">{pct(app.uptime_7d)}</div><div className="metric__label">Up, 7 days</div></div>
        <div><div className="metric__value">{app.latency_ms_24h == null ? "–" : `${app.latency_ms_24h} ms`}</div><div className="metric__label">Response</div></div>
      </div>
      <div className="status-strip" role="img" aria-label={`Last 24 hours: ${app.hours.filter((h) => h === "down").length} hours with an outage`}>
        {app.hours.map((h, i) => <span key={i} className={`status-strip__cell status-strip__cell--${h ?? "none"}`} />)}
      </div>
      <div className="status-strip__legend muted"><span>24 h ago</span><span>now</span></div>
      {app.incidents.length > 0 ? (
        <ul className="items" aria-label="Recent outages">
          {app.incidents.map((inc) => (
            <li key={inc.at} className="item">
              <span className="item__dot dot-critical" aria-hidden="true" />
              <span className="item__text">
                <div className="item__title">Down {when(inc.at)}{inc.minutes != null ? ` for ${inc.minutes < 60 ? `${inc.minutes} min` : `${Math.round(inc.minutes / 6) / 10} h`}` : " (still down)"}</div>
                <div className="item__subtitle">{inc.detail}</div>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        app.samples > 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}><Activity size={13} aria-hidden="true" style={{ verticalAlign: "-2px" }} /> No outages in the last 7 days.</p>
      )}
    </Glass>
  );
}

/** Backups, a waiting SirisAI update and certificates running out (3.6). */
function UpkeepCard() {
  const { data } = useResource("hub:upkeep", () => fitness.upkeep(), { staleMs: 10 * 60_000, persist: true });
  if (!data) return null;
  const b = data.sirisai?.backups;
  const u = data.sirisai?.update;
  const certs = data.certificates.filter((c) => c.days_left !== null);
  const ago = (iso: string) => {
    const hours = Math.round((Date.now() - new Date(iso).getTime()) / 3_600_000);
    return hours < 1 ? "just now" : hours < 48 ? `${hours} h ago` : `${Math.round(hours / 24)} days ago`;
  };
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Upkeep">
      <header className="widget__head"><HardDrive aria-hidden="true" /><span>Upkeep</span></header>
      <ul className="items">
        <li className="item">
          <span className={`item__dot ${!b ? "" : b.stale || !b.newest ? "dot-critical" : "dot-good"}`} aria-hidden="true" />
          <span className="item__text">
            <div className="item__title">SirisAI backups</div>
            <div className="item__subtitle">{!data.sirisai ? "SirisAI didn't answer (2.14 or later reports this)" : !b ? "Not set up" : b.newest ? `Newest ${ago(b.newest)} · ${b.count} kept${b.stale ? " · too old" : ""}` : "None yet"}</div>
          </span>
        </li>
        {u && (
          <li className="item">
            <span className={`item__dot ${u.available ? "dot-warning" : "dot-good"}`} aria-hidden="true" />
            <span className="item__text">
              <div className="item__title">SirisAI {u.current}</div>
              <div className="item__subtitle">{u.available ? `${u.latest} is out: update from the Inbox` : "Up to date"}</div>
            </span>
          </li>
        )}
        <li className="item">
          <span className="item__dot dot-good" aria-hidden="true" />
          <span className="item__text"><div className="item__title">SirisOS {data.sirisos.version}</div></span>
        </li>
        {certs.map((c) => (
          <li key={c.host} className="item">
            <span className={`item__dot ${c.warning ? "dot-warning" : "dot-good"}`} aria-hidden="true" />
            <span className="item__text">
              <div className="item__title">Certificate · {c.host}</div>
              <div className="item__subtitle">{c.days_left! < 0 ? "Expired" : `Runs out in ${c.days_left} days`}</div>
            </span>
          </li>
        ))}
      </ul>
    </Glass>
  );
}
