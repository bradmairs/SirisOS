import { useEffect, useState } from "react";
import { Activity, CalendarClock, Clock3, CloudSun, Cpu, Package, ShieldCheck } from "lucide-react";
import { assistant } from "../api/hub";
import type { HubApp, Hud } from "../api/types";
import { Glass } from "../components/Glass";

const HUD_REFRESH_MS = 60_000;

/** SirisAI's HUD summary (weather, server, calendar, activity), refreshed every minute. */
export function useHud() {
  const [hud, setHud] = useState<Hud | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    const load = () =>
      assistant
        .hud()
        .then((h) => {
          if (!live) return;
          setHud(h);
          setFailed(false);
        })
        .catch(() => live && setFailed(true));
    load();
    const timer = window.setInterval(() => document.visibilityState === "visible" && load(), HUD_REFRESH_MS);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, []);
  return { hud, failed };
}

function Card({ title, Icon, wide, delay = 0, children }: { title: string; Icon: typeof Clock3; wide?: boolean; delay?: number; children: React.ReactNode }) {
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

export function ClockWidget({ delay }: { delay?: number }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <Card title="Local time" Icon={Clock3} delay={delay}>
      <div className="hud-clock">
        {now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false })}
        <span className="hud-clock__sec">{String(now.getSeconds()).padStart(2, "0")}</span>
      </div>
      <p className="muted" style={{ margin: 0 }}>
        {now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
      </p>
    </Card>
  );
}

export function WeatherWidget({ weather, delay }: { weather: NonNullable<Hud["weather"]>; delay?: number }) {
  return (
    <Card title="Outside" Icon={CloudSun} delay={delay}>
      <div className="row" style={{ alignItems: "baseline", gap: 12 }}>
        <span className="hud-big">{Math.round(weather.temperature_c)}°</span>
        <span className="hud-cond">{weather.conditions}</span>
      </div>
      <div className="metrics metrics--compact">
        {weather.humidity_percent != null && <Metric label="Humidity" value={`${weather.humidity_percent}%`} />}
        {weather.wind_speed_kmh != null && <Metric label="Wind" value={`${Math.round(weather.wind_speed_kmh)} km/h`} />}
        {weather.precipitation_mm != null && <Metric label="Rain" value={`${weather.precipitation_mm} mm`} />}
      </div>
    </Card>
  );
}

export function ServerWidget({ system, delay }: { system: NonNullable<Hud["system"]>; delay?: number }) {
  const disk = system.disk?.["/"] ?? Object.values(system.disk ?? {})[0];
  const temps = system.temperatures_celsius ?? {};
  const cpuTemp = temps["coretemp:Package id 0"] ?? (Object.keys(temps).length ? Math.max(...Object.values(temps)) : null);
  return (
    <Card title="Home server" Icon={Cpu} delay={delay}>
      <div className="rings">
        <Ring label="CPU" percent={system.cpu_percent} />
        {system.memory && <Ring label="Memory" percent={system.memory.percent_used} detail={`${system.memory.used_gb.toFixed(1)} / ${system.memory.total_gb.toFixed(0)} GB`} />}
        {disk && <Ring label="Disk" percent={disk.percent_used} detail={`${Math.round(disk.used_gb)} / ${Math.round(disk.total_gb)} GB`} />}
      </div>
      {cpuTemp != null && <p className="muted" style={{ margin: 0 }}>CPU package {Math.round(cpuTemp)}°C · {system.cpu_count} threads</p>}
    </Card>
  );
}

export function AppHealthWidget({ apps, delay }: { apps: HubApp[]; delay?: number }) {
  const count = (state: HubApp["status"]["state"]) => apps.filter((a) => a.status.state === state).length;
  const ok = count("ok");
  const problems = apps.filter((a) => a.status.state === "degraded" || a.status.state === "down");
  return (
    <Card title="Siris apps" Icon={ShieldCheck} delay={delay}>
      <div className="metrics metrics--compact">
        <Metric label="Online" value={String(ok)} tone="good" />
        <Metric label="Need attention" value={String(problems.length)} tone={problems.length ? "warning" : undefined} />
        <Metric label="Not set up" value={String(count("unconfigured"))} />
      </div>
      {problems.length > 0 && (
        <ul className="items">
          {problems.slice(0, 3).map((a) => (
            <li key={a.id} className="item">
              <span className={`item__dot state-${a.status.state}`} aria-hidden="true" />
              <span className="item__text">
                <div className="item__title">{a.name}</div>
                <div className="item__subtitle">{a.status.detail}</div>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function ComingUpWidget({ events, delay }: { events: NonNullable<Hud["next_events"]>; delay?: number }) {
  return (
    <Card title="Coming up" Icon={CalendarClock} delay={delay}>
      {events.length === 0 ? (
        <p className="muted">Nothing on the calendar.</p>
      ) : (
        <ul className="items">
          {events.slice(0, 5).map((e, i) => (
            <li key={`${e.summary}-${i}`} className="item">
              <span className="item__dot" aria-hidden="true" />
              <span className="item__text">
                <div className="item__title">{e.summary}</div>
                <div className="item__subtitle">{formatWhen(e.start)}</div>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function ActivityWidget({ entries, delay }: { entries: NonNullable<Hud["autonomy"]>; delay?: number }) {
  return (
    <Card title="Siris activity" Icon={Activity} delay={delay}>
      {entries.length === 0 ? (
        <p className="muted">Siris hasn't acted on its own yet today.</p>
      ) : (
        <ul className="items hud-log">
          {entries.slice(-5).reverse().map((e, i) => (
            <li key={`${e.time}-${i}`} className="item">
              <span className="hud-log__time">{e.local_time}</span>
              <span className="item__text">
                <div className="item__title">{capitalise(e.what)}</div>
                <div className="item__subtitle">{e.outcome}</div>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function ParcelsWidget({ parcels, delay }: { parcels: NonNullable<Hud["parcels"]>; delay?: number }) {
  return (
    <Card title="Parcels" Icon={Package} delay={delay}>
      <ul className="items">
        {parcels.slice(0, 4).map((p, i) => (
          <li key={i} className="item">
            <span className="item__dot" aria-hidden="true" />
            <span className="item__text">
              <div className="item__title">{String(p.description ?? p.name ?? p.carrier ?? "Parcel")}</div>
              {p.status != null && <div className="item__subtitle">{String(p.status)}</div>}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "good" | "warning" | "critical" }) {
  return (
    <div>
      <div className={`metric__value ${tone ? `tone-${tone}` : ""}`}>{value}</div>
      <div className="metric__label">{label}</div>
    </div>
  );
}

export function Ring({ label, percent, detail }: { label: string; percent: number; detail?: string }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const p = Math.max(0, Math.min(100, percent));
  const tone = p >= 90 ? "var(--critical)" : p >= 75 ? "var(--warning)" : "var(--accent)";
  return (
    <figure className="ring" title={detail}>
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="32" cy="32" r={r} className="ring__track" />
        <circle cx="32" cy="32" r={r} className="ring__value" style={{ stroke: tone, strokeDasharray: `${(p / 100) * c} ${c}` }} />
        <text x="32" y="36" textAnchor="middle" className="ring__text">{Math.round(p)}%</text>
      </svg>
      <figcaption>{label}</figcaption>
    </figure>
  );
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  const time = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
  return sameDay ? `Today ${time}` : `${d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })} ${time}`;
}

function capitalise(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}
