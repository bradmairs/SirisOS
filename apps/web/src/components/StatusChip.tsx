import type { AppStatus } from "../api/types";

const LABEL: Record<AppStatus["state"], string> = {
  ok: "Running",
  degraded: "Needs attention",
  down: "Unreachable",
  unconfigured: "Not configured",
};

export function StatusChip({ status }: { status: AppStatus }) {
  return (
    <span className="chip">
      <span className={`dot state-${status.state}`} aria-hidden="true" />
      {LABEL[status.state]}
      {status.latency_ms != null && status.state === "ok" && <span style={{ opacity: 0.6 }}>· {status.latency_ms} ms</span>}
    </span>
  );
}
