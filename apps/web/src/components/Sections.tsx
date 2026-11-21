import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Brain, BriefcaseBusiness, Dumbbell, HeartPulse, House, HousePlug, LayoutGrid, ListTodo, MoonStar, Server, Sparkles, Wallet, FileText,
} from "lucide-react";

/** 10.5: the side menu's groups. Screens that belong together share one entry and a row of tabs; every screen keeps its own
 * address, so links, notifications and Shortcuts still work. The phone tab bar and search still list every screen (NAV). */

export interface SectionTab { to: string; label: string; end?: boolean }
export interface Section { id: string; label: string; Icon: typeof House; tabs: SectionTab[] }
export interface SectionGroup { heading: string | null; sections: Section[] }

export const SECTIONS: SectionGroup[] = [
  { heading: null, sections: [
    { id: "home", label: "Home", Icon: House, tabs: [{ to: "/", label: "Home", end: true }] },
  ] },
  { heading: "Daily", sections: [
    { id: "tasks", label: "Tasks", Icon: ListTodo, tabs: [{ to: "/tasks", label: "Tasks" }, { to: "/projects", label: "Projects" }] },
    { id: "gym", label: "SirisGym", Icon: Dumbbell, tabs: [{ to: "/gym", label: "SirisGym" }] },
    { id: "reviews", label: "Reviews", Icon: MoonStar, tabs: [{ to: "/wrapup", label: "Tonight" }, { to: "/review", label: "This week" }, { to: "/year", label: "This year" }] },
  ] },
  { heading: "You", sections: [
    { id: "health", label: "Health", Icon: HeartPulse, tabs: [{ to: "/health", label: "Health" }, { to: "/fitness", label: "Fitness" }] },
    { id: "budget", label: "Budget", Icon: Wallet, tabs: [{ to: "/budget", label: "Budget" }] },
  ] },
  { heading: "Home & life", sections: [
    { id: "household", label: "Household", Icon: HousePlug, tabs: [{ to: "/week", label: "Around the week" }, { to: "/meals", label: "Meals" }, { to: "/house", label: "Smart Home" }] },
    { id: "life", label: "Life Admin", Icon: FileText, tabs: [{ to: "/life", label: "Life Admin" }, { to: "/travel", label: "Trips" }, { to: "/things", label: "Things & People" }] },
  ] },
  { heading: "Work", sections: [
    { id: "work", label: "Work", Icon: BriefcaseBusiness, tabs: [{ to: "/work", label: "Work" }, { to: "/engineering", label: "Engineering" }, { to: "/career", label: "Career" }] },
  ] },
  { heading: "Siris", sections: [
    { id: "assistant", label: "SirisAI", Icon: Sparkles, tabs: [{ to: "/assistant", label: "SirisAI" }] },
    { id: "brain", label: "Siris", Icon: Brain, tabs: [{ to: "/brain", label: "Siris" }] },
    { id: "links", label: "Links", Icon: LayoutGrid, tabs: [{ to: "/links", label: "Links" }] },
  ] },
  { heading: "Server", sections: [
    { id: "server", label: "Server", Icon: Server, tabs: [{ to: "/status", label: "Status" }, { to: "/homelab", label: "Home Lab" }, { to: "/terminal", label: "Terminal" }, { to: "/security", label: "Security" }] },
  ] },
];

const ALL = SECTIONS.flatMap((g) => g.sections);

const matches = (tab: SectionTab, path: string) => (tab.end ? path === tab.to : path === tab.to || path.startsWith(`${tab.to}/`));

/** The section (and tab) a path belongs to. */
export function sectionFor(path: string): { section: Section; tab: SectionTab } | null {
  for (const section of ALL) {
    const tab = section.tabs.find((t) => matches(t, path));
    if (tab) return { section, tab };
  }
  return null;
}

const KEY = "sirisos.section.";

/** Where a section's menu entry goes: the tab last used in it on this device, else its first. */
export function sectionHref(section: Section): string {
  try {
    const last = localStorage.getItem(KEY + section.id);
    if (last && section.tabs.some((t) => t.to === last)) return last;
  } catch { /* private mode */ }
  return section.tabs[0].to;
}

export function rememberTab(path: string) {
  const hit = sectionFor(path);
  if (!hit || hit.section.tabs.length < 2) return;
  try { localStorage.setItem(KEY + hit.section.id, hit.tab.to); } catch { /* private mode */ }
}

/** The row of tabs above a screen that shares its section with others. */
export function SectionTabs() {
  const { pathname } = useLocation();
  const hit = sectionFor(pathname);
  useEffect(() => rememberTab(pathname), [pathname]);
  if (!hit || hit.section.tabs.length < 2) return null;
  return (
    <nav className="section-tabs" aria-label={hit.section.label}>
      {hit.section.tabs.map((t) => (
        <Link key={t.to} to={t.to} className={`section-tabs__tab${t === hit.tab ? " section-tabs__tab--on" : ""}`} aria-current={t === hit.tab ? "page" : undefined}>
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
