import type { HubApp } from "../api/types";
import { Glass } from "./Glass";
import { hueFor, iconFor } from "./icons";

export function AppIcon({ app, size = 64 }: { app: Pick<HubApp, "id" | "icon" | "status">; size?: number }) {
  const Icon = iconFor(app.icon);
  const hue = hueFor(app.id);
  return (
    <Glass
      className="app-icon"
      style={{
        width: size,
        height: size,
        borderRadius: size * 0.28,
        color: hue,
        background: `radial-gradient(120% 120% at 30% 10%, color-mix(in srgb, ${hue} 30%, transparent), color-mix(in srgb, ${hue} 8%, transparent) 70%)`,
      }}
    >
      <Icon strokeWidth={2} aria-hidden="true" style={{ width: size * 0.44, height: size * 0.44 }} />
      {app.status.state !== "ok" && (
        <span className={`app-icon__badge state-${app.status.state}`} aria-hidden="true" />
      )}
    </Glass>
  );
}
