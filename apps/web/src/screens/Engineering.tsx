import { useState } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { BookOpen, Calculator, ChevronRight, Droplets, FolderOpen, type LucideIcon } from "lucide-react";
import type { HubApp } from "../api/types";
import { Glass } from "../components/Glass";
import { PageHead } from "../components/PageHead";
import { AppGrid, useApps } from "./Home";
import { AppSheet } from "./AppSheet";
import { CalculatorScreen, Calculators } from "./engineering/Calculators";
import { Hydro } from "./engineering/Hydro";
import { ProjectScreen, Projects } from "./engineering/Projects";
import { Standards } from "./engineering/Standards";

const TOOLS: { to: string; title: string; detail: string; Icon: LucideIcon; hue: string }[] = [
  { to: "hydro", title: "SirisHydro", detail: "Ask your standards library, with citations", Icon: Droplets, hue: "#38bdf8" },
  { to: "calculators", title: "Calculators", detail: "Manning, Rational Method, headloss, pumps, buoyancy…", Icon: Calculator, hue: "#fbbf24" },
  { to: "standards", title: "Standards", detail: "Upload, search and cite authority standards", Icon: BookOpen, hue: "#2dd4bf" },
  { to: "projects", title: "Projects", detail: "Group calculations and the standards behind them", Icon: FolderOpen, hue: "#a78bfa" },
];

export function Engineering() {
  return (
    <Routes>
      <Route index element={<EngineeringHome />} />
      <Route path="hydro" element={<Hydro />} />
      <Route path="calculators" element={<Calculators />} />
      <Route path="calculators/:id" element={<CalculatorScreen />} />
      <Route path="standards" element={<Standards />} />
      <Route path="projects" element={<Projects />} />
      <Route path="projects/:id" element={<ProjectScreen />} />
    </Routes>
  );
}

function EngineeringHome() {
  const { apps } = useApps(false);
  const [open, setOpen] = useState<HubApp | null>(null);
  const engineering = (apps ?? []).filter((a) => a.category === "engineering");
  return (
    <>
      <PageHead eyebrow="Civil & water" title="Engineering" />
      <div className="widget-grid">
        {TOOLS.map(({ to, title, detail, Icon, hue }, i) => (
          <Glass key={to} as={Link} to={to} interactive className="tool-card" style={{ animationDelay: `${i * 40}ms` }}>
            <span className="tool-card__icon" style={{ color: hue, background: `color-mix(in srgb, ${hue} 18%, transparent)` }}>
              <Icon aria-hidden="true" />
            </span>
            <span className="item__text">
              <span className="tool-card__title">{title}</span>
              <span className="tool-card__detail">{detail}</span>
            </span>
            <ChevronRight size={18} className="muted" aria-hidden="true" />
          </Glass>
        ))}
      </div>
      {engineering.length > 0 && (
        <>
          <h2 className="section-title">Apps</h2>
          <AppGrid apps={engineering} onOpen={setOpen} />
        </>
      )}
      {open && <AppSheet appId={open.id} initial={open} onClose={() => setOpen(null)} />}
    </>
  );
}
