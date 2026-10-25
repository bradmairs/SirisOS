import { NavLink } from "react-router-dom";
import { adaptive, homeContext, localPhase, type HomeContext } from "../api/home";
import { useResource } from "../api/resource";
import { Glass } from "./Glass";
import { NAV } from "./Sidebar";

/** The tab bar's last slot follows where you are and the part of the day (4.94): Career in
 *  work hours, Smart home when you're home outside them, Career otherwise. Like Home, it stays
 *  put when "Changes with the time of day" is off. */
export function dockItems(ctx: Pick<HomeContext, "phase" | "home"> | null, adapt = true): typeof NAV {
  const items = NAV.filter((n) => n.dock !== false);
  if (!adapt) return items;
  const phase = ctx?.phase ?? localPhase();
  if (phase === "work" || ctx?.home !== true) return items;
  const house = NAV.find((n) => n.to === "/house")!;
  return items.map((n) => (n.to === "/career" ? house : n));
}

/** Phone tab bar. Wide screens use the sidebar instead (hidden in CSS). */
export function Dock() {
  // The same context Home reads (shared and cached), so the two agree.
  const ctx = useResource<HomeContext>("home:context", () => homeContext(), { refreshMs: 5 * 60_000, persist: true });
  return (
    <Glass as="nav" shape="pill" className="dock" aria-label="Main">
      {dockItems(ctx.data ?? null, adaptive()).map(({ to, label, Icon, end }) => (
        <NavLink key={to} to={to} end={end} className="dock__item">
          <Icon size={22} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </NavLink>
      ))}
    </Glass>
  );
}
