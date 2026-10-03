import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { RefreshCw, Sparkles } from "lucide-react";
import { hub } from "../api/hub";
import { useResource } from "../api/resource";
import { session } from "../api/client";
import type { HubApp } from "../api/types";
import { isWidget } from "../api/types";
import { AppIcon } from "../components/AppIcon";
import { Glass } from "../components/Glass";
import { WidgetCard } from "../components/WidgetCard";
import { AppSheet } from "./AppSheet";
import { ActivityWidget, AppHealthWidget, ClockWidget, ComingUpWidget, ParcelsWidget, ServerWidget, WeatherWidget, useHud } from "./HudWidgets";

const REFRESH_MS = 60_000;

export function greeting(date = new Date()): string {
  const h = date.getHours();
  if (h < 5) return "Good night";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

/** Every app tile with its widget. One shared, polled request serves the
 * sidebar, Home and Engineering (see api/resource.ts). */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function useApps(_widgets = true) {
  const { data, error, loading, reload } = useResource("hub:apps", (fresh) => hub.apps({ widgets: true, fresh }), { refreshMs: REFRESH_MS });
  return { apps: data ?? null, error: data ? null : error, refreshing: loading, reload: (fresh = false) => reload(fresh).catch(() => undefined) };
}

export function AppGrid({ apps, onOpen }: { apps: HubApp[]; onOpen: (app: HubApp) => void }) {
  return (
    <div className="app-grid">
      {apps.map((app, i) => (
        <button
          key={app.id}
          className={`app-tile ${app.status.state === "unconfigured" ? "app-tile--dim" : ""}`}
          style={{ animationDelay: `${i * 30}ms` }}
          onClick={() => onOpen(app)}
          aria-label={`${app.name}: ${app.status.state}`}
        >
          <AppIcon app={app} />
          <span className="app-tile__name">{app.name}</span>
        </button>
      ))}
    </div>
  );
}

export function Home() {
  const { apps, error, refreshing, reload } = useApps(true);
  const { hud } = useHud();
  const [open, setOpen] = useState<HubApp | null>(null);
  const [ask, setAsk] = useState("");
  const navigate = useNavigate();
  const now = new Date();

  const widgets = useMemo(() => (apps ?? []).filter((a) => a.widget && (isWidget(a.widget) || a.status.state !== "unconfigured")), [apps]);
  const attention = (apps ?? []).filter((a) => a.status.state === "degraded" || a.status.state === "down").length;

  function submitAsk(e: FormEvent) {
    e.preventDefault();
    if (ask.trim()) navigate(`/assistant?q=${encodeURIComponent(ask.trim())}`);
  }

  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">
            {now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}
          </p>
          <h1 className="page-head__title">
            {greeting(now)}
            {session.user() ? `, ${capitalise(session.user()!)}` : ""}
          </h1>
        </div>
        <Glass as="button" shape="pill" interactive className="button button--icon" onClick={() => reload(true)} aria-label="Refresh">
          <RefreshCw className={refreshing ? "spin" : ""} aria-hidden="true" />
        </Glass>
      </header>

      <Glass as="form" shape="pill" className="ask-bar" onSubmit={submitAsk} role="search">
        <Sparkles aria-hidden="true" />
        <input className="ask-bar__input" placeholder="Ask Siris anything…" value={ask} onChange={(e) => setAsk(e.target.value)} aria-label="Ask Siris" />
      </Glass>

      {error && <div className="error-banner" role="alert" style={{ marginTop: 16 }}>{error}</div>}
      {attention > 0 && (
        <p className="muted" style={{ margin: "14px 6px 0" }}>
          {attention} app{attention === 1 ? " needs" : "s need"} attention: tap a badged icon for details.
        </p>
      )}

      <h2 className="section-title">Now</h2>
      <div className="widget-grid">
        <ClockWidget />
        {hud?.weather && <WeatherWidget weather={hud.weather} delay={40} />}
        {hud?.system && <ServerWidget system={hud.system} delay={80} />}
        {apps && <AppHealthWidget apps={apps} delay={120} />}
      </div>

      {apps === null && !error ? (
        <div className="widget-grid" style={{ marginTop: 22 }}>
          {[0, 1, 2].map((i) => (
            <Glass key={i} className="widget">
              <div className="skeleton" style={{ height: 14, width: "40%" }} />
              <div className="skeleton" style={{ height: 34, width: "70%" }} />
              <div className="skeleton" style={{ height: 14, width: "90%" }} />
            </Glass>
          ))}
        </div>
      ) : (
        <>
          <h2 className="section-title">Today</h2>
          <div className="widget-grid">
            {hud?.next_events && <ComingUpWidget events={hud.next_events} />}
            {widgets.map((app, i) => (
              <WidgetCard key={app.id} app={app} delay={i * 50} />
            ))}
            {hud?.autonomy && <ActivityWidget entries={hud.autonomy} />}
            {hud?.parcels && hud.parcels.length > 0 && <ParcelsWidget parcels={hud.parcels} />}
          </div>
          {apps && apps.length > 0 && (
            <>
              <h2 className="section-title">Apps</h2>
              <AppGrid apps={apps} onOpen={setOpen} />
            </>
          )}
        </>
      )}
      {open && <AppSheet appId={open.id} initial={open} onClose={() => setOpen(null)} />}
    </>
  );
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
