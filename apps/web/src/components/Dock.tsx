import { NavLink } from "react-router-dom";
import { Glass } from "./Glass";
import { NAV } from "./Sidebar";

/** Phone tab bar. Wide screens use the sidebar instead (hidden in CSS). */
export function Dock() {
  return (
    <Glass as="nav" shape="pill" className="dock" aria-label="Main">
      {NAV.map(({ to, label, Icon, end }) => (
        <NavLink key={to} to={to} end={end} className="dock__item">
          <Icon size={22} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </NavLink>
      ))}
    </Glass>
  );
}
