import { Fragment, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity, CalendarClock, CloudSun, Cpu, House, RefreshCw, ShieldCheck, SlidersHorizontal, Sparkles, Sunrise, WifiOff } from "lucide-react";
import { hub } from "../api/hub";
import { EMPTY_LAYOUT, arrange, home, type DeviceLayout, type HomeLayout } from "../api/home";
import { oldestUpdate, useResource } from "../api/resource";
import { useOnline } from "../api/online";
import { session } from "../api/client";
import type { HubApp } from "../api/types";
import { isWidget } from "../api/types";
import { AppIcon } from "../components/AppIcon";
import { Glass } from "../components/Glass";
import { LoadingWidget, WidgetCard } from "../components/WidgetCard";
import { AppSheet } from "./AppSheet";
import { HomeCustomise, type SectionInfo } from "./HomeCustomise";
import { CareerWidget } from "./CareerWidget";
import { InboxPanel } from "../components/Inbox";
import { ActivityWidget, AppHealthWidget, ClockWidget, ComingUpWidget, ServerWidget, WeatherWidget, useHud } from "./HudWidgets";
import { CamerasWidget, CarWidget, EnergyWidget, ProtocolsWidget, SirisParcelsWidget, useSirisWidgets } from "./SirisControls";

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
  const { data, error, loading, reload } = useResource("hub:apps", (fresh) => hub.appsWithGuest({ widgets: true, fresh }), { refreshMs: REFRESH_MS, persist: true });
  return {
    apps: data?.apps ?? null,
    // SirisAI's guest mode (ADR 110): personal widgets are already left out by the hub.
    guest: !!data?.guest_mode,
    error: data ? null : error,
    /** Showing the last good list because the latest refresh failed. */
    stale: !!data && !!error,
    refreshing: loading,
    reload: (fresh = false) => reload(fresh).catch(() => undefined),
  };
}

/** True on phone-width screens (where the dock replaces the sidebar). */
export function useIsPhone(): boolean {
  const query = "(max-width: 959px)";
  const supported = typeof window !== "undefined" && typeof window.matchMedia === "function";
  const [phone, setPhone] = useState(() => supported && window.matchMedia(query).matches);
  useEffect(() => {
    if (!supported) return;
    const mq = window.matchMedia(query);
    const onChange = () => setPhone(mq.matches);
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, [supported]);
  return phone;
}

/** The saved Home layout (order and hidden widgets per device), shared and
 * saved optimistically: the change shows at once and is written behind. */
export function useHomeLayout(device: "phone" | "desktop") {
  const { data, mutate, reload } = useResource<HomeLayout>("home:layout", () => home.layout(), { staleMs: 60_000, persist: true });
  const layout = data ?? EMPTY_LAYOUT;
  const save = (next: DeviceLayout) => {
    const doc = { ...layout, [device]: next };
    mutate(doc);
    home.saveLayout(doc).catch(() => reload(true).catch(() => undefined));
  };
  return { layout: layout[device], save };
}

/** One widget's place on Home: `node` is null when it has nothing to show. */
interface Slot {
  id: string;
  label: string;
  node: ReactNode;
}

function arrangeSlots(slots: Slot[], layout: DeviceLayout) {
  const present = slots.filter((s) => s.node);
  const byId = new Map(present.map((s) => [s.id, s]));
  const ordered = arrange(present.map((s) => s.id), layout.order).map((id) => byId.get(id)!);
  const hidden = new Set(layout.hidden);
  return { all: ordered, shown: ordered.filter((s) => !hidden.has(s.id)) };
}

export function AppGrid({ apps, onOpen, layout = "grid" }: { apps: HubApp[]; onOpen: (app: HubApp) => void; layout?: "grid" | "strip" }) {
  return (
    <div className={`app-grid${layout === "strip" ? " app-grid--strip" : ""}`}>
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
  const { apps, guest, error, stale, refreshing, reload } = useApps(true);
  const online = useOnline();
  const { hud, loading: hudLoading } = useHud();
  const { widgets: siris, loading: sirisLoading, reload: reloadSiris } = useSirisWidgets();
  const appsLoading = apps === null && !error;
  const hideMine = guest || !!siris?.guest_mode;
  const [open, setOpen] = useState<HubApp | null>(null);
  const [ask, setAsk] = useState("");
  const phone = useIsPhone();
  const device = phone ? "phone" : "desktop";
  const { layout, save: saveLayout } = useHomeLayout(device);
  const [customising, setCustomising] = useState(false);
  const navigate = useNavigate();
  const now = new Date();

  const widgets = useMemo(() => (apps ?? []).filter((a) => a.widget && (isWidget(a.widget) || a.status.state !== "unconfigured")), [apps]);
  const attention = (apps ?? []).filter((a) => a.status.state === "degraded" || a.status.state === "down").length;

  // Until a source answers, its widgets hold their place with a "Loading…" card.
  const nowSlots: Slot[] = [
    { id: "clock", label: "Local time", node: <ClockWidget /> },
    { id: "weather", label: "Outside", node: hud?.weather ? <WeatherWidget weather={hud.weather} delay={40} /> : hudLoading && <LoadingWidget title="Outside" Icon={CloudSun} delay={40} /> },
    { id: "server", label: "Home server", node: hud?.system ? <ServerWidget system={hud.system} delay={80} /> : hudLoading && <LoadingWidget title="Home server" Icon={Cpu} delay={80} /> },
    { id: "app-health", label: "Siris apps", node: apps ? <AppHealthWidget apps={apps} delay={120} /> : appsLoading && <LoadingWidget title="Siris apps" Icon={ShieldCheck} delay={120} /> },
  ];
  const today: Slot[] = [
    { id: "coming-up", label: "Coming up", node: !hideMine && (hud?.next_events ? <ComingUpWidget events={hud.next_events} /> : hudLoading && <LoadingWidget title="Coming up" Icon={CalendarClock} />) },
    { id: "career", label: "Career", node: !hideMine && <CareerWidget delay={30} /> },
    ...(appsLoading
      ? [0, 1].map((i) => ({ id: `loading-app-${i}`, label: "Loading apps", node: <LoadingWidget title="Loading apps" delay={60 + i * 50} /> }))
      : widgets.map((app, i) => ({ id: `app:${app.id}`, label: app.name, node: <WidgetCard app={app} delay={i * 50} /> }))),
    { id: "activity", label: "Siris activity", node: hud?.autonomy ? <ActivityWidget entries={hud.autonomy} /> : hudLoading && <LoadingWidget title="Siris activity" Icon={Activity} /> },
    { id: "parcels", label: "Parcels", node: siris?.parcels && siris.parcels.length > 0 && <SirisParcelsWidget parcels={siris.parcels} /> },
  ];
  const homeControls: Slot[] = sirisLoading
    ? [{ id: "loading-home", label: "Home controls", node: <LoadingWidget title="Home controls" Icon={House} wide /> }]
    : [
        { id: "protocols", label: "Protocols", node: siris && siris.protocols.length > 0 && <ProtocolsWidget protocols={siris.protocols} lastRun={siris.last_protocol} onChanged={reloadSiris} /> },
        { id: "cameras", label: "Cameras", node: siris && siris.cameras.length > 0 && <CamerasWidget cameras={siris.cameras} /> },
        { id: "car", label: "Car", node: siris?.car && <CarWidget car={siris.car} /> },
        { id: "energy", label: "Power", node: siris?.energy && <EnergyWidget energy={siris.energy} /> },
      ];
  const sections = [
    { title: "Now", slots: arrangeSlots(nowSlots, layout) },
    { title: "Today", slots: arrangeSlots(today, layout) },
    { title: "Home", slots: arrangeSlots(homeControls, layout) },
  ];
  // Placeholders aren't widgets you can arrange.
  const editable: SectionInfo[] = sections.map(({ title, slots }) => ({
    title,
    slots: slots.all.filter((slot) => !slot.id.startsWith("loading-")).map(({ id, label }) => ({ id, label })),
  })).filter((section) => section.slots.length > 0);

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
        <div className="row">
          <Glass as={Link} to="/brief" shape="pill" interactive className="button button--small brief-entry" aria-label="Today's brief">
            <Sunrise aria-hidden="true" /> <span>Today's brief</span>
          </Glass>
          <Glass as="button" shape="pill" interactive className="button button--icon" onClick={() => reload(true)} aria-label="Refresh">
            <RefreshCw className={refreshing ? "spin" : ""} aria-hidden="true" />
          </Glass>
        </div>
      </header>

      <Glass as="form" shape="pill" className="ask-bar" onSubmit={submitAsk} role="search">
        <Sparkles aria-hidden="true" />
        <input className="ask-bar__input" placeholder="Ask Siris anything…" value={ask} onChange={(e) => setAsk(e.target.value)} aria-label="Ask Siris" />
      </Glass>

      {phone && apps && apps.length > 0 && (
        <section className="app-suite" aria-label="Siris App Suite">
          <h2 className="section-title">Siris App Suite</h2>
          <AppGrid apps={apps} onOpen={setOpen} layout="strip" />
        </section>
      )}

      {hideMine && (
        <p className="guest-banner" role="status">Guest mode is on: your calendar, email, health and notes are hidden.</p>
      )}
      <InboxPanel />

      {(!online || stale) && apps && <OfflineNote online={online} />}
      {error && <div className="error-banner" role="alert" style={{ marginTop: 16 }}>{error}</div>}
      {attention > 0 && (
        <p className="muted" style={{ margin: "14px 6px 0" }}>
          {attention} app{attention === 1 ? " needs" : "s need"} attention: tap a badged icon for details.
        </p>
      )}

      {sections.map(({ title, slots }) =>
        slots.shown.length > 0 && (
          <section key={title} aria-label={title}>
            <h2 className="section-title">{title}</h2>
            <div className="widget-grid">
              {slots.shown.map((slot) => <Fragment key={slot.id}>{slot.node}</Fragment>)}
            </div>
          </section>
        ),
      )}
      <div className="customise-entry">
        <Glass as="button" shape="pill" interactive className="button button--small" onClick={() => setCustomising(true)}>
          <SlidersHorizontal aria-hidden="true" /> <span>Customise Home</span>
        </Glass>
      </div>
      {!phone && apps && apps.length > 0 && (
        <>
          <h2 className="section-title">Siris App Suite</h2>
          <AppGrid apps={apps} onOpen={setOpen} />
        </>
      )}
      {open && <AppSheet appId={open.id} initial={open} onClose={() => setOpen(null)} />}
      {customising && <HomeCustomise device={device} sections={editable} layout={layout} onChange={saveLayout} onClose={() => setCustomising(false)} />}
    </>
  );
}

const HOME_KEYS = ["hub:apps", "sirisai:hud", "sirisai:widgets", "career:overview"];

/** "Offline · as of 7:42": Home is showing what it last fetched. */
function OfflineNote({ online }: { online: boolean }) {
  const at = oldestUpdate(HOME_KEYS);
  const when = at ? new Date(at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : null;
  const day = at && new Date(at).toDateString() !== new Date().toDateString() ? new Date(at).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" }) + " " : "";
  return (
    <p className="offline-note" role="status">
      <WifiOff size={15} aria-hidden="true" /> {online ? "Can't reach SirisOS" : "Offline"}
      {when ? ` · showing what it had at ${day}${when}` : ""}
    </p>
  );
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
