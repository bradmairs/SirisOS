import {
  AppWindow,
  Archive,
  Brain,
  Calculator,
  ClipboardCheck,
  Clock,
  Drone,
  Dumbbell,
  Film,
  FolderKanban,
  Server,
  Sparkles,
  Users,
  type LucideIcon,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  sparkles: Sparkles,
  brain: Brain,
  kanban: FolderKanban,
  "clipboard-check": ClipboardCheck,
  archive: Archive,
  clock: Clock,
  drone: Drone,
  users: Users,
  dumbbell: Dumbbell,
  film: Film,
  server: Server,
  calculator: Calculator,
};

/** Each app's glyph colour on its glass icon. */
const HUES: Record<string, string> = {
  sirisai: "#5fd3ff",
  "second-brain": "#a78bfa",
  "apd-pm": "#60a5fa",
  reviewer: "#fbbf24",
  archive: "#2dd4bf",
  gvw: "#4ade80",
  cmp: "#818cf8",
  sirisdrone: "#38bdf8",
  jefit: "#fb923c",
  helmarr: "#f472b6",
  "neo-server": "#22d3ee",
};

export function iconFor(name: string): LucideIcon {
  return ICONS[name] ?? AppWindow;
}

export function hueFor(appId: string): string {
  return HUES[appId] ?? "var(--accent)";
}
