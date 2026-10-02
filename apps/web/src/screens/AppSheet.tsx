import { useEffect, useState } from "react";
import { ExternalLink, RefreshCw } from "lucide-react";
import { hub } from "../api/hub";
import type { HubApp } from "../api/types";
import { isWidget } from "../api/types";
import { AppIcon } from "../components/AppIcon";
import { Glass } from "../components/Glass";
import { Sheet } from "../components/Sheet";
import { StatusChip } from "../components/StatusChip";
import { WidgetCard } from "../components/WidgetCard";

export function AppSheet({ appId, initial, onClose }: { appId: string; initial: HubApp; onClose: () => void }) {
  const [app, setApp] = useState<HubApp>(initial);
  const [loading, setLoading] = useState(false);

  async function load(fresh: boolean) {
    setLoading(true);
    try {
      setApp(await hub.app(appId, fresh));
    } catch {
      /* keep what we have */
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!initial.launch_only) load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appId]);

  return (
    <Sheet label={app.name} onClose={onClose}>
      <div className="app-sheet__head">
        <AppIcon app={app} size={76} />
        <div style={{ minWidth: 0 }}>
          <h2 className="app-sheet__name">{app.name}</h2>
          <p className="muted" style={{ margin: "2px 0 8px" }}>{app.description}</p>
          <div className="row" style={{ flexWrap: "wrap" }}>
            <StatusChip status={app.status} />
            {app.status.version && <span className="chip">{app.status.version}</span>}
          </div>
        </div>
      </div>

      {app.status.detail && app.status.state !== "ok" && (
        <p className={{ unconfigured: "muted", degraded: "warning-banner", down: "error-banner", ok: "muted" }[app.status.state]} style={{ marginTop: 16 }}>{app.status.detail}</p>
      )}

      {isWidget(app.widget) && (
        <div style={{ marginTop: 18 }}>
          <WidgetCard app={app} showSource={false} />
        </div>
      )}

      <div className="row" style={{ marginTop: 22 }}>
        {app.launch_url ? (
          <Glass as="a" variant="tint" shape="pill" interactive className="button" href={app.launch_url} target="_blank" rel="noreferrer" style={{ flex: 1 }}>
            Open {app.name} <ExternalLink aria-hidden="true" />
          </Glass>
        ) : (
          <span className="muted" style={{ flex: 1 }}>No launch link configured.</span>
        )}
        {!app.launch_only && (
          <Glass as="button" shape="pill" interactive className="button button--icon" onClick={() => load(true)} aria-label="Check again" disabled={loading}>
            <RefreshCw className={loading ? "spin" : ""} aria-hidden="true" />
          </Glass>
        )}
      </div>
    </Sheet>
  );
}
