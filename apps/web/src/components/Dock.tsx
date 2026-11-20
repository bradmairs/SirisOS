import { useCallback, useEffect, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { Sunrise } from "lucide-react";
import { brain } from "../api/hub";
import { adaptive, homeContext, localPhase, type DayPhase, type HomeContext } from "../api/home";
import { useResource } from "../api/resource";
import type { InboxItem } from "../api/types";
import { Glass } from "./Glass";
import { useInbox } from "./Inbox";
import { NAV } from "./Sidebar";

type Tab = (typeof NAV)[number];

function reducedMotion(): boolean {
  return !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/** Every screen a tab can be, with the short labels the bar has room for. */
const SCREENS: Record<string, Tab> = {
  ...Object.fromEntries(NAV.map((n) => [n.to, n])),
  "/brief": { to: "/brief", label: "Brief", Icon: Sunrise, end: false },
};
const SHORT: Record<string, string> = { "/review": "Review", "/year": "Year", "/status": "Status", "/engineering": "Engineering" };
const tab = (to: string): Tab => ({ ...SCREENS[to], label: SHORT[to] ?? SCREENS[to].label });

/**
 * The tab bar follows where you are and the part of the day (4.94, 4.95). The first three are
 * always Home, SirisAI and Siris. Unless you've picked them in Times of day:
 * - the fourth is the brief in the morning, Wrap Up from wind down, and Links otherwise;
 * - the fifth is Work in work hours (8:00 to 4:30 on weekdays; 7.2), Smart Home when you're home,
 *   Tasks when you're out, and Career when SirisAI can't tell.
 * - from 6 to 8 am, SirisGym takes the fifth (or the fourth, if you've picked the fifth; 6.97).
 * With "Changes with the time of day" off it's Links and Career all day.
 */
export function dockItems(ctx: Pick<HomeContext, "phase" | "home" | "dock"> | null, adapt = true, at = new Date()): Tab[] {
  const fixed = NAV.filter((n) => n.dock !== false && n.to !== "/links" && n.to !== "/career");
  if (!adapt) return [...fixed, tab("/links"), tab("/career")];
  const phase: DayPhase = ctx?.phase ?? localPhase();
  const fourth = ctx?.dock?.fourth && ctx.dock.fourth !== "auto" ? ctx.dock.fourth
    : phase === "morning" ? "/brief" : phase === "winddown" || phase === "night" ? "/wrapup" : "/links";
  const fifth = ctx?.dock?.fifth && ctx.dock.fifth !== "auto" ? ctx.dock.fifth
    : phase === "work" ? "/work" : ctx?.home === true ? "/house" : ctx?.home === false ? "/tasks" : "/career";
  const slots = [fourth, fifth];
  if (gymTime(at) && !slots.includes("/gym")) {
    const free = ctx?.dock?.fifth && ctx.dock.fifth !== "auto" ? (ctx.dock.fourth && ctx.dock.fourth !== "auto" ? -1 : 0) : 1;
    if (free >= 0) slots[free] = "/gym";
  }
  return [...fixed, ...slots.filter((to) => SCREENS[to]).map(tab)];
}

/** Gym time on the tab bar: 6:00 to 7:59 am, by this device's clock. */
export function gymTime(at: Date): boolean {
  return at.getHours() >= 6 && at.getHours() < 8;
}

// Inbox items about the house: the intruder and presence checks, Home Assistant, cameras, protocols.
const HOME_SOURCE = /intruder|presence|departure|home_assistant|camera|frigate|protocol|doorbell|garage|lock/i;

/** Which tabs have something waiting (4.95): Siris when the brain's inbox has notes to sort or a
 *  brain item is open, Smart Home when the house wants you. */
export function dockBadges(items: Pick<InboxItem, "source" | "app">[], brainInbox: number): Record<string, string> {
  const badges: Record<string, string> = {};
  const brainItems = items.filter((i) => i.source === "second-brain").length;
  if (brainItems + brainInbox > 0) badges["/brain"] = `${brainItems + brainInbox} waiting in the brain`;
  const house = items.filter((i) => HOME_SOURCE.test(`${i.source} ${i.app}`)).length;
  if (house > 0) badges["/house"] = `${house} thing${house === 1 ? "" : "s"} at home need${house === 1 ? "s" : ""} you`;
  return badges;
}

/** Phone tab bar. Wide screens use the sidebar instead (hidden in CSS). */
export function Dock() {
  // The same context Home reads (shared and cached), so the two agree.
  const ctx = useResource<HomeContext>("home:context", () => homeContext(), { refreshMs: 5 * 60_000, persist: true });
  const brainInbox = useResource("brain:inbox:count", () => brain.inboxCount(), { staleMs: 600_000, persist: true });
  const { items } = useInbox();
  const badges = dockBadges(items, brainInbox.data?.count ?? 0);
  // The bar changes on the clock, not only when data does; back from the background counts too.
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const tick = () => setNow(new Date());
    const timer = window.setInterval(tick, 30_000);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", tick);
    };
  }, []);
  const location = useLocation();
  const navigate = useNavigate();
  const tabs = dockItems(ctx.data ?? null, adaptive(), now);
  const active = activeTab(tabs, location.pathname);

  // 10.3: one bubble (the "lens") that slides to the tab you're on, and follows your finger when you drag along the
  // bar, like iOS's Liquid Glass tab bar. Let go over a tab to open it.
  const bar = useRef<HTMLElement>(null);
  const [spots, setSpots] = useState<{ x: number; w: number }[]>([]);
  const [drag, setDrag] = useState<{ x: number; over: number } | null>(null);
  const gesture = useRef({ id: -1, startX: 0, moved: false, over: -1, swallowClick: false });

  const measure = useCallback(() => {
    const el = bar.current;
    if (!el) return;
    const items = Array.from(el.querySelectorAll<HTMLElement>(".dock__item"));
    setSpots(items.map((i) => ({ x: i.offsetLeft, w: i.offsetWidth })));
  }, []);
  useLayoutEffect(measure, [measure, tabs.map((t) => t.to).join("|")]);
  useEffect(() => {
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure]);

  const overAt = (clientX: number): number => {
    const el = bar.current;
    if (!el || !spots.length) return -1;
    const x = clientX - el.getBoundingClientRect().left;
    let best = 0;
    spots.forEach((s, i) => { if (x >= s.x) best = i; });
    return best;
  };
  const down = (e: ReactPointerEvent<HTMLElement>) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    gesture.current = { id: e.pointerId, startX: e.clientX, moved: false, over: overAt(e.clientX), swallowClick: false };
  };
  const move = (e: ReactPointerEvent<HTMLElement>) => {
    const g = gesture.current;
    if (g.id !== e.pointerId) return;
    if (!g.moved && Math.abs(e.clientX - g.startX) < 8) return;
    if (!g.moved) {
      g.moved = true;
      bar.current?.setPointerCapture?.(e.pointerId);  // only once it's a drag, so a plain tap still taps the tab
    }
    const el = bar.current;
    if (!el || !spots.length) return;
    const over = overAt(e.clientX);
    if (over !== g.over) {
      g.over = over;
      navigator.vibrate?.(8);
    }
    const w = spots[over]?.w ?? spots[0].w;
    const left = e.clientX - el.getBoundingClientRect().left - w / 2;
    const max = spots[spots.length - 1].x;
    setDrag({ x: Math.min(max, Math.max(spots[0].x, left)), over });
  };
  const up = (e: ReactPointerEvent<HTMLElement>) => {
    const g = gesture.current;
    if (g.id !== e.pointerId) return;
    g.id = -1;
    if (!g.moved) return;
    g.swallowClick = true;
    window.setTimeout(() => { g.swallowClick = false; }, 80);
    setDrag(null);
    const to = tabs[g.over]?.to;
    if (to && g.over !== active) navigate(to);
  };
  const cancel = () => { gesture.current.id = -1; setDrag(null); };

  const spot = drag ? { x: drag.x, w: spots[drag.over]?.w ?? 0 } : active >= 0 ? spots[active] : undefined;
  return (
    <Glass as="nav" shape="pill" className={`dock${drag ? " dock--dragging" : ""}`} aria-label="Main" ref={bar}
      onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={cancel}
      onClickCapture={(e: React.MouseEvent) => { if (gesture.current.swallowClick) { e.preventDefault(); e.stopPropagation(); } }}>
      {spot && <span className="dock__lens" aria-hidden="true" style={{ transform: `translateX(${spot.x}px)`, width: spot.w }} />}
      {tabs.map(({ to, label, Icon, end }, i) => (
        <NavLink key={to} to={to} end={end} className={`dock__item${drag?.over === i ? " dock__item--over" : ""}`} aria-label={badges[to] ? `${label}: ${badges[to]}` : undefined}
          onClick={(e) => {
            // 9.8: tapping the tab you're already on goes back to the top of the page, as in iOS apps.
            if (location.pathname === to && !location.search) {
              e.preventDefault();
              window.scrollTo({ top: 0, behavior: reducedMotion() ? "auto" : "smooth" });
            }
          }}>
          <span className="dock__icon">
            <Icon size={22} strokeWidth={2} aria-hidden="true" />
            {badges[to] && <span className="dock__dot" aria-hidden="true" />}
          </span>
          <span>{label}</span>
        </NavLink>
      ))}
    </Glass>
  );
}

/** Which tab is the page you're on (as NavLink decides it), or -1. */
export function activeTab(tabs: Pick<Tab, "to" | "end">[], pathname: string): number {
  return tabs.findIndex((t) => (t.end ? pathname === t.to : pathname === t.to || pathname.startsWith(`${t.to}/`)));
}
