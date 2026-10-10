import { NavLink } from "react-router-dom";
import { Glass } from "./Glass";
import { NAV } from "./Sidebar";

/** Phone tab bar. Wide screens use the sidebar instead (hidden in CSS). */
export function Dock() {
  return (
    <Glass as="nav" shape="pill" className="dock" aria-label="Main">
      {NAV.map(({ to, label, short, Icon, end }) => (
        <NavLink key={to} to={to} end={end} className="dock__item" aria-label={label}>
          <Icon size={22} strokeWidth={2} aria-hidden="true" />
          {short ? (
            <>
              <span className="dock__label--long">{label}</span>
              <span className="dock__label--short" aria-hidden="true">{short}</span>
            </>
          ) : (
            <span>{label}</span>
          )}
        </NavLink>
      ))}
    </Glass>
  );
}
