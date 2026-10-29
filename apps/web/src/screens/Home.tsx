import { Fragment, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity, CalendarClock, Clock3, CloudSun, Cpu, House, RefreshCw, ShieldCheck, SlidersHorizontal, Sparkles, Sunrise, WifiOff } from "lucide-react";
import { hub } from "../api/hub";
import { DAY_HIDDEN, EMPTY_LAYOUT, adaptive, arrange, hiddenNow, home, homeContext, localPhase, sectionOrder, setAdaptive, type DeviceLayout, type HomeContext, type HomeLayout } from "../api/home";
import { oldestUpdate, useResource } from "../api/resource";
import { useOnline } from "../api/online";
import { session } from "../api/client";
import type { HubApp, Hud, SirisCar } from "../api/types";
import { isWidget } from "../api/types";
import { AppIcon } from "../components/AppIcon";
import { Glass } from "../components/Glass";
import { LoadingWidget, WidgetCard } from "../components/WidgetCard";
import { AppSheet } from "./AppSheet";
import { HomeCustomise, type SectionInfo } from "./HomeCustomise";
import { HomeTimes } from "./HomeTimes";
import { TasksWidget } from "./TasksWidget";
import { FocusCard } from "./FocusCard";
import { BrainTodayWidget, CaptureWidget, ResurfaceWidget } from "./DayWidgets";
import { FitnessWidget } from "./FitnessWidget";
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

/** Server health worth a look: a busy CPU, full memory or a full disk, or running hot. */
function serverNeedsYou(system: Hud["system"] | undefined): boolean {
  if (!system) return false;
  const disks = Object.values(system.disk ?? {}).some((d) => d.percent_used >= 90);
  const hot = Object.values(system.temperatures_celsius ?? {}).some((t) => t >= 80);
  return system.cpu_percent >= 85 || (system.memory?.percent_used ?? 0) >= 90 || disks || hot;
}

/** The car wants plugging in tonight: low, or under half and not on charge. */
function carNeedsCharge(car: SirisCar | null | undefined): boolean {
  if (!car) return false;
  return car.low_battery || (car.battery_percent != null && car.battery_percent < 50 && !car.plugged_in && !car.charging);
}

/** Coming up for the part of the day (4.9): this morning, the rest of the work day, tonight and
 *  tomorrow morning, or today on a weekend. The context's events, else the HUD's next few. */
function dayEvents(phase: string, ctx: HomeContext | null, hud: Hud["next_events"] | undefined, now: Date): NonNullable<Hud["next_events"]> | undefined {
  if (!ctx?.events) return hud;
  const day = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const today = day(now), tomorrow = day(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1));
  const hour = (iso: string) => (iso.includes("T") ? new Date(iso).getHours() : 0);
  const ahead = (iso: string) => !iso.includes("T") || new Date(iso).getTime() > now.getTime() - 15 * 60_000;
  const keep = ctx.events.filter((e) => {
    const on = e.start.slice(0, 10);
    if (phase === "morning") return on === today && ahead(e.start) && hour(e.start) < 12;
    if (phase === "work" || phase === "weekend") return on === today && ahead(e.start);
    return (on === today && ahead(e.start)) || (on === tomorrow && hour(e.start) < 12);
  });
  return keep.map((e) => ({ summary: e.title, start: e.start }));
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
  const [timing, setTiming] = useState(false);
  const [adapt, setAdapt] = useState(adaptive);
  const ctxRes = useResource<HomeContext>("home:context", () => homeContext(), { refreshMs: 5 * 60_000, persist: true });
  const ctx = ctxRes.data ?? null;
  const navigate = useNavigate();
  const now = new Date();

  const widgets = useMemo(() => (apps ?? []).filter((a) => a.widget && (isWidget(a.widget) || a.status.state !== "unconfigured")), [apps]);
  const phase = ctx?.phase ?? localPhase();
  const [showAll, setShowAll] = useState(false);
  // Tasks and Coming up follow the part of the day (4.9): work tasks in work hours, yours after.
  const taskArea = phase === "work" ? "work" : phase === "morning" ? undefined : "personal";
  const comingUp = dayEvents(phase, ctx, hud?.next_events, now);
  const attention = (apps ?? []).filter((a) => a.status.state === "degraded" || a.status.state === "down").length;

  // Until a source answers, its widgets hold their place with a "Loading…" card.
  const nowSlots: Slot[] = [
    { id: "clock", label: "Local time", node: <ClockWidget /> },
    { id: "weather", label: "Outside", node: hud?.weather ? <WeatherWidget weather={hud.weather} delay={40} /> : hudLoading && <LoadingWidget title="Outside" Icon={CloudSun} delay={40} /> },
    { id: "server", label: "Home server", node: hud?.system ? <ServerWidget system={hud.system} delay={80} /> : hudLoading && <LoadingWidget title="Home server" Icon={Cpu} delay={80} /> },
    { id: "app-health", label: "Siris apps", node: apps ? <AppHealthWidget apps={apps} delay={120} /> : appsLoading && <LoadingWidget title="Siris apps" Icon={ShieldCheck} delay={120} /> },
  ];
  const today: Slot[] = [
    { id: "tasks", label: "Tasks", node: !hideMine && <TasksWidget delay={20} area={adapt ? taskArea : undefined} /> },
    { id: "coming-up", label: "Coming up", node: !hideMine && (comingUp ? <ComingUpWidget events={comingUp} /> : hudLoading && <LoadingWidget title="Coming up" Icon={CalendarClock} />) },
    { id: "career", label: "Career", node: !hideMine && <CareerWidget delay={30} /> },
    { id: "fitness", label: "Fitness", node: !hideMine && <FitnessWidget delay={40} /> },
    ...(appsLoading
      ? [0, 1].map((i) => ({ id: `loading-app-${i}`, label: "Loading apps", node: <LoadingWidget title="Loading apps" delay={60 + i * 50} /> }))
      : widgets.map((app, i) => ({ id: `app:${app.id}`, label: app.name, node: <WidgetCard app={app} delay={i * 50} /> }))),
    { id: "activity", label: "SirisAI activity", node: hud?.autonomy ? <ActivityWidget entries={hud.autonomy} /> : hudLoading && <LoadingWidget title="SirisAI activity" Icon={Activity} /> },
    { id: "parcels", label: "Parcels", node: siris?.parcels && siris.parcels.length > 0 && <SirisParcelsWidget parcels={siris.parcels} /> },
    { id: "brain", label: "Learned today", node: !hideMine && hud?.brain && <BrainTodayWidget items={hud.brain} /> },
    { id: "resurface", label: "From your notes", node: !hideMine && <ResurfaceWidget /> },
    { id: "capture", label: "Quick capture", node: !hideMine && <CaptureWidget /> },
  ];
  // Lights and scenes are left to Siri and the Home app (4.8); protocols show while you're home
  // (or when SirisAI can't tell).
  const atHome = ctx?.home !== false;
  const homeControls: Slot[] = sirisLoading
    ? [{ id: "loading-home", label: "Home", node: <LoadingWidget title="Home" Icon={House} wide /> }]
    : [
        { id: "protocols", label: "Protocols (while you're home)", node: atHome && siris && siris.protocols.length > 0 && <ProtocolsWidget protocols={siris.protocols} lastRun={siris.last_protocol} onChanged={reloadSiris} /> },
        { id: "cameras", label: "Cameras", node: siris && siris.cameras.length > 0 && <CamerasWidget cameras={siris.cameras} /> },
        { id: "car", label: "Car", node: siris?.car && <CarWidget car={siris.car} /> },
        { id: "energy", label: "Power", node: siris?.energy && <EnergyWidget energy={siris.energy} /> },
      ];
  const sectionList = [
    { title: "Now", slots: arrangeSlots(nowSlots, layout) },
    { title: "Today", slots: arrangeSlots(today, layout) },
    { title: "Home", slots: arrangeSlots(homeControls, layout) },
  ];
  // What this part of the day leaves out (4.9), unless you asked for everything; some widgets only
  // show when they need you. Customise Home's own hiding applies on top, on every part of the day.
  const dayHidden = ctx?.hidden ?? DAY_HIDDEN[phase];
  const quiet = (id: string) => {
    if (id === "server") return phase !== "weekend" && !serverNeedsYou(hud?.system);
    if (id === "app-health") return attention === 0;
    if (id === "energy") return !(siris?.energy && (siris.energy.cheap_now || siris.energy.waiting_jobs > 0));
    if (id === "car") return phase === "evening" && !carNeedsCharge(siris?.car);
    return false;
  };
  const leftOut = (id: string) => adapt && !showAll && !id.startsWith("loading-") && (hiddenNow(id, dayHidden) || quiet(id));
  const daySections = sectionList.map((sec) => ({ ...sec, slots: { ...sec.slots, shown: sec.slots.shown.filter((slot) => !leftOut(slot.id)) } }));
  const leftOutCount = sectionList.reduce((n, sec) => n + sec.slots.shown.filter((slot) => leftOut(slot.id)).length, 0);
  // The part of the day decides which section leads (3.1); widgets inside keep your order.
  const order = sectionOrder(phase, ctx);
  const sections = adapt ? [...daySections].sort((a, b) => order.indexOf(a.title) - order.indexOf(b.title)) : daySections;
  const editableSource = sectionList;
  // Placeholders aren't widgets you can arrange.
  const editable: SectionInfo[] = editableSource.map(({ title, slots }) => ({
    title,
    slots: slots.all.filter((slot) => !slot.id.startsWith("loading-")).map(({ id, label }) => ({ id, label })),
  })).filter((section) => section.slots.length > 0);

  function submitAsk(e: FormEvent) {
    e.preventDefault();
    if (ask.trim()) navigate(`/assistant?q=${encodeURIComponent(ask.trim())}`);
  }

  return (
    <div className={`home${adapt && (phase === "winddown" || phase === "night") ? " home--quiet" : ""}`}>
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
        <input className="ask-bar__input" placeholder="Ask SirisAI anything…" value={ask} onChange={(e) => setAsk(e.target.value)} aria-label="Ask SirisAI" />
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

      {adapt && ctx && !hideMine && <FocusCard ctx={ctx} events={hud?.next_events} parcels={siris?.parcels?.length ?? 0} inbox={siris?.attention?.open ?? 0} />}

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
      {adapt && (leftOutCount > 0 || showAll) && (
        <button type="button" className="show-more home__everything" onClick={() => setShowAll(!showAll)}>
          {showAll ? "Show less" : `Show everything (${leftOutCount} more)`}
        </button>
      )}
      <div className="customise-entry">
        <Glass as="button" shape="pill" interactive className="button button--small" onClick={() => setCustomising(true)}>
          <SlidersHorizontal aria-hidden="true" /> <span>Customise Home</span>
        </Glass>
        <button type="button" className="show-more" onClick={() => { setAdaptive(!adapt); setAdapt(!adapt); }}>
          {adapt ? "Changes with the time of day · turn off" : "Same order all day · let it change with the time of day"}
        </button>
        {adapt && (
          <button type="button" className="show-more" onClick={() => setTiming(true)}>
            <Clock3 size={13} aria-hidden="true" /> Times of day
          </button>
        )}
      </div>
      {!phone && apps && apps.length > 0 && (
        <>
          <h2 className="section-title">Siris App Suite</h2>
          <AppGrid apps={apps} onOpen={setOpen} />
        </>
      )}
      {open && <AppSheet appId={open.id} initial={open} onClose={() => setOpen(null)} />}
      {timing && <HomeTimes onClose={() => setTiming(false)} onSaved={() => ctxRes.reload(true).catch(() => undefined)} />}
      {customising && <HomeCustomise device={device} sections={editable} layout={layout} onChange={saveLayout} onClose={() => setCustomising(false)} />}
    </div>
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
