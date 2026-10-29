import { NavLink } from "react-router-dom";
import { Sunrise } from "lucide-react";
import { brain } from "../api/hub";
import { adaptive, homeContext, localPhase, type DayPhase, type HomeContext } from "../api/home";
import { useResource } from "../api/resource";
import type { BrainInsights, InboxItem } from "../api/types";
import { Glass } from "./Glass";
import { useInbox } from "./Inbox";
import { NAV } from "./Sidebar";

type Tab = (typeof NAV)[number];

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
 * - the fourth is the brief in the morning, Wrap up from wind down, and Links otherwise;
 * - the fifth is Career in work hours, Smart home when you're home, Tasks when you're out,
 *   and Career when SirisAI can't tell.
 * With "Changes with the time of day" off it's Links and Career all day.
 */
export function dockItems(ctx: Pick<HomeContext, "phase" | "home" | "dock"> | null, adapt = true): Tab[] {
  const fixed = NAV.filter((n) => n.dock !== false && n.to !== "/links" && n.to !== "/career");
  if (!adapt) return [...fixed, tab("/links"), tab("/career")];
  const phase: DayPhase = ctx?.phase ?? localPhase();
  const fourth = ctx?.dock?.fourth && ctx.dock.fourth !== "auto" ? ctx.dock.fourth
    : phase === "morning" ? "/brief" : phase === "winddown" || phase === "night" ? "/wrapup" : "/links";
  const fifth = ctx?.dock?.fifth && ctx.dock.fifth !== "auto" ? ctx.dock.fifth
    : phase === "work" ? "/career" : ctx?.home === true ? "/house" : ctx?.home === false ? "/tasks" : "/career";
  return [...fixed, ...[fourth, fifth].filter((to) => SCREENS[to]).map(tab)];
}

// Inbox items about the house: the intruder and presence checks, Home Assistant, cameras, protocols.
const HOME_SOURCE = /intruder|presence|departure|home_assistant|camera|frigate|protocol|doorbell|garage|lock/i;

/** Which tabs have something waiting (4.95): Siris when the brain's inbox has notes to sort or a
 *  brain item is open, Smart home when the house wants you. */
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
  const insights = useResource<BrainInsights>("brain:insights", () => brain.insights(), { staleMs: 600_000 });
  const { items } = useInbox();
  const badges = dockBadges(items, insights.data?.inbox?.count ?? 0);
  return (
    <Glass as="nav" shape="pill" className="dock" aria-label="Main">
      {dockItems(ctx.data ?? null, adaptive()).map(({ to, label, Icon, end }) => (
        <NavLink key={to} to={to} end={end} className="dock__item" aria-label={badges[to] ? `${label}: ${badges[to]}` : undefined}>
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
