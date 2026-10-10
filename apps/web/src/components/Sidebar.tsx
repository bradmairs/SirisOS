import { useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { ArrowUpRight, Award, Brain, House, Inbox, LayoutGrid, LogOut, Ruler, Search, Sparkles, Sunrise, X } from "lucide-react";
import { InboxBadge } from "./Inbox";
import type { HubApp } from "../api/types";
import { Glass } from "./Glass";
import { Logo } from "./Logo";
import { hueFor, iconFor } from "./icons";

/** Every screen, in the sidebar. `dock: false` keeps one off the phone tab bar, which fits five. */
export const NAV: { to: string; label: string; Icon: typeof House; end: boolean; dock?: boolean }[] = [
  { to: "/", label: "Home", Icon: House, end: true },
  { to: "/assistant", label: "Siris", Icon: Sparkles, end: false },
  { to: "/brain", label: "Brain", Icon: Brain, end: false },
  { to: "/links", label: "Links", Icon: LayoutGrid, end: false },
  { to: "/engineering", label: "Engineering", Icon: Ruler, end: false, dock: false },
  { to: "/career", label: "Career", Icon: Award, end: false },
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
}: {
  apps: HubApp[] | null;
  user: string | null;
  open: boolean;
  onClose: () => void;
  onSignOut: () => void;
  onSearch?: () => void;
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

  const launchable = (apps ?? []).filter((a) => a.launch_url);

  return (
    <>
      <div className={`sidebar-scrim ${open ? "sidebar-scrim--open" : ""}`} onClick={onClose} aria-hidden="true" />
      <Glass as="aside" variant="strong" shape="xl" className={`sidebar ${open ? "sidebar--open" : ""}`} aria-label="Menu">
        <div className="sidebar__brand">
          <Logo size={38} />
          <button type="button" className="icon-link sidebar__close" onClick={onClose} aria-label="Close menu">
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {onSearch && (
          <button type="button" className="sidebar__search" onClick={onSearch}>
            <Search size={16} aria-hidden="true" />
            <span>Search</span>
            <kbd className="sidebar__kbd" aria-hidden="true">{isMac() ? "⌘K" : "Ctrl K"}</kbd>
          </button>
        )}

        <nav className="sidebar__nav" aria-label="Screens">
          {NAV.map(({ to, label, Icon, end }) => (
            <NavLink key={to} to={to} end={end} className="sidebar__link">
              <Icon size={19} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
          <NavLink to="/inbox" className="sidebar__link">
            <Inbox size={19} aria-hidden="true" />
            <span>Inbox</span>
            <InboxBadge />
          </NavLink>
          <NavLink to="/brief" className="sidebar__link">
            <Sunrise size={19} aria-hidden="true" />
            <span>Today's brief</span>
          </NavLink>
        </nav>

        {launchable.length > 0 && (
          <>
            <p className="sidebar__label">Apps</p>
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

        <div className="sidebar__foot">
          <span className="sidebar__user">{user ? user.charAt(0).toUpperCase() + user.slice(1) : ""}</span>
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
