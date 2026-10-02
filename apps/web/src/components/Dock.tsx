import { NavLink } from "react-router-dom";
import { Brain, House, Ruler, Sparkles } from "lucide-react";
import { Glass } from "./Glass";

const TABS = [
  { to: "/", label: "Home", Icon: House, end: true },
  { to: "/assistant", label: "Siris", Icon: Sparkles, end: false },
  { to: "/brain", label: "Brain", Icon: Brain, end: false },
  { to: "/engineering", label: "Engineering", Icon: Ruler, end: false },
];

export function Dock() {
  return (
    <Glass as="nav" shape="pill" className="dock" aria-label="Main">
      {TABS.map(({ to, label, Icon, end }) => (
        <NavLink key={to} to={to} end={end} className="dock__item">
          <Icon size={22} strokeWidth={2} aria-hidden="true" />
          <span>{label}</span>
        </NavLink>
      ))}
    </Glass>
  );
}
