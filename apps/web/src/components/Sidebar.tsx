import { Fragment, useEffect } from "react";
import { SECTIONS, sectionFor, sectionHref } from "./Sections";
import { AskAbout } from "./AskAbout";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Activity, ArrowUpRight, Award, Brain, CalendarRange, ChartColumn, Dumbbell, FileText, FolderKanban, Package, Wallet, Footprints, HeartPulse, House, HousePlug, PenLine, Inbox, LayoutGrid, ListTodo, LogOut, MoonStar, Ruler, Search, ShieldCheck, Sparkles, SquareTerminal, Sunrise, X, BriefcaseBusiness, Network, Plane, UtensilsCrossed, CalendarHeart, CloudOff } from "lucide-react";
import { openOffline } from "./SyncBar";
import { InboxBadge } from "./Inbox";
import type { HubApp } from "../api/types";
import { Glass } from "./Glass";
import { Logo } from "./Logo";
import { APP_VERSION } from "../version";
import { hueFor, iconFor } from "./icons";

/** Every screen, in the sidebar. `dock: false` keeps one off the phone tab bar, which fits five. */
export const NAV: { to: string; label: string; Icon: typeof House; end: boolean; dock?: boolean }[] = [
  { to: "/", label: "Home", Icon: House, end: true },
  { to: "/tasks", label: "Tasks", Icon: ListTodo, end: false, dock: false },
  { to: "/gym", label: "SirisGym", Icon: Dumbbell, end: false, dock: false },
  { to: "/projects", label: "Projects", Icon: FolderKanban, end: false, dock: false },
  { to: "/house", label: "Smart Home", Icon: HousePlug, end: false, dock: false },
  { to: "/wrapup", label: "Wrap Up", Icon: MoonStar, end: false, dock: false },
  { to: "/review", label: "Weekly Review", Icon: CalendarRange, end: false, dock: false },
  { to: "/year", label: "Your Year", Icon: ChartColumn, end: false, dock: false },
  { to: "/health", label: "Health", Icon: HeartPulse, end: false, dock: false },
  { to: "/life", label: "Life Admin", Icon: FileText, end: false, dock: false },
  { to: "/budget", label: "Budget", Icon: Wallet, end: false, dock: false },
  { to: "/meals", label: "Meals", Icon: UtensilsCrossed, end: false, dock: false },
  { to: "/week", label: "Around the Week", Icon: CalendarHeart, end: false, dock: false },
  { to: "/travel", label: "Trips", Icon: Plane, end: false, dock: false },
  { to: "/things", label: "Things & People", Icon: Package, end: false, dock: false },
  { to: "/fitness", label: "Fitness", Icon: Footprints, end: false, dock: false },
  { to: "/assistant", label: "SirisAI", Icon: Sparkles, end: false },
  { to: "/brain", label: "Siris", Icon: Brain, end: false },
  { to: "/links", label: "Links", Icon: LayoutGrid, end: false },
  { to: "/work", label: "Work", Icon: BriefcaseBusiness, end: false, dock: false },
  { to: "/engineering", label: "Engineering", Icon: Ruler, end: false, dock: false },
  { to: "/career", label: "Career", Icon: Award, end: false },
  { to: "/status", label: "System Status", Icon: Activity, end: false, dock: false },
  { to: "/homelab", label: "Home Lab", Icon: Network, end: false, dock: false },
  { to: "/terminal", label: "Terminal", Icon: SquareTerminal, end: false, dock: false },
  { to: "/security", label: "Security", Icon: ShieldCheck, end: false, dock: false },
];

/**
 * The side menu: logo top-left, the four screens, then every connected app as
 * a launch link with its live status. Always visible on wide screens; a drawer
 * on phones (opened from the top bar).
 */
export function Sidebar({
  apps,
  user,
  open,
  onClose,
  onSignOut,
  onSearch,
  onCapture,
}: {
  apps: HubApp[] | null;
  user: string | null;
  open: boolean;
  onClose: () => void;
  onSignOut: () => void;
  onSearch?: () => void;
  onCapture?: () => void;
}) {
  const location = useLocation();
  useEffect(() => {
    onClose();
  }, [location.pathname, onClose]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const current = sectionFor(location.pathname);
  const launchable = (apps ?? []).filter((a) => a.launch_url);

  return (
    <>
      <div className={`sidebar-scrim ${open ? "sidebar-scrim--open" : ""}`} onClick={onClose} aria-hidden="true" />
      <Glass as="aside" variant="strong" shape="xl" className={`sidebar ${open ? "sidebar--open" : ""}`} aria-label="Menu">
        <div className="sidebar__brand">
          <Link to="/" className="sidebar__home" onClick={onClose} aria-label="SirisOS home">
            <Logo size={38} />
          </Link>
          <button type="button" className="icon-link sidebar__close" onClick={onClose} aria-label="Close menu">
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {/* The list scrolls inside the panel, so the glass (and its edge) stays the full height (5.71). */}
        <div className="sidebar__scroll">
        {onSearch && (
          <button type="button" className="sidebar__search" onClick={onSearch}>
            <Search size={16} aria-hidden="true" />
            <span>Search</span>
            <kbd className="sidebar__kbd" aria-hidden="true">{isMac() ? "⌘K" : "Ctrl K"}</kbd>
          </button>
        )}
        {onCapture && (
          <button type="button" className="sidebar__search" onClick={onCapture}>
            <PenLine size={16} aria-hidden="true" />
            <span>Quick capture</span>
          </button>
        )}
        <AskAbout variant="sidebar" />

        <nav className="sidebar__nav" aria-label="Screens">
          {SECTIONS.map((g) => (
            <Fragment key={g.heading ?? "top"}>
              {g.heading && <p className="sidebar__group">{g.heading}</p>}
              {g.sections.map((sec) => (
                <Link key={sec.id} to={sectionHref(sec)} className={`sidebar__link${current?.section.id === sec.id ? " active" : ""}`} aria-current={current?.section.id === sec.id ? "page" : undefined}>
                  <sec.Icon size={19} aria-hidden="true" />
                  <span>{sec.label}</span>
                </Link>
              ))}
            </Fragment>
          ))}
          <p className="sidebar__group">More</p>
          <NavLink to="/inbox" className="sidebar__link">
            <Inbox size={19} aria-hidden="true" />
            <span>Inbox</span>
            <InboxBadge />
          </NavLink>
          <NavLink to="/brief" className="sidebar__link">
            <Sunrise size={19} aria-hidden="true" />
            <span>Today's brief</span>
          </NavLink>
          <button type="button" className="sidebar__link" style={{ border: 0, background: "none", width: "100%", font: "inherit", cursor: "pointer" }} onClick={() => { onClose(); openOffline(); }}>
            <CloudOff size={19} aria-hidden="true" />
            <span>Offline</span>
          </button>
        </nav>

        {launchable.length > 0 && (
          <>
            <p className="sidebar__label">Siris App Suite</p>
            <ul className="sidebar__apps">
              {launchable.map((app) => {
                const Icon = iconFor(app.icon);
                return (
                  <li key={app.id}>
                    <a className="sidebar__link sidebar__link--app" href={app.launch_url!} target="_blank" rel="noreferrer" title={app.status.detail || app.name}>
                      <Icon size={17} style={{ color: hueFor(app.id) }} aria-hidden="true" />
                      <span>{app.name}</span>
                      <span className={`sidebar__state state-${app.status.state}`} aria-label={app.status.state} />
                      <ArrowUpRight size={14} className="sidebar__out" aria-hidden="true" />
                    </a>
                  </li>
                );
              })}
            </ul>
          </>
        )}
        </div>

        <div className="sidebar__foot">
          <span className="sidebar__user">
            {user ? user.charAt(0).toUpperCase() + user.slice(1) : ""}
            <span className="sidebar__version">SirisOS {APP_VERSION}</span>
          </span>
          <button type="button" className="icon-link" onClick={onSignOut} aria-label="Sign out" title="Sign out">
            <LogOut size={17} aria-hidden="true" />
          </button>
        </div>
      </Glass>
    </>
  );
}

function isMac(): boolean {
  return typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
}
