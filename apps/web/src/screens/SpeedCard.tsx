import { Gauge } from "lucide-react";
import { useResource } from "../api/resource";
import { life, type Job } from "../api/life";
import { Glass } from "../components/Glass";

const STAGES: [string, string][] = [
  ["first_word", "First word"], ["total", "Whole reply"], ["model", "Model"], ["context", "Gathering context"],
  ["tools", "Choosing tools"], ["tool", "Running the tool"], ["answer", "Writing the answer"],
];

const secs = (ms: number | null | undefined) => (ms == null ? "–" : ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`);

function jobNote(j: Job) {
  if (j.last_error) return `failed: ${j.last_error}`;
  if (j.slow) return "running slow";
  if (j.running) return "running";
  return j.last_seconds != null ? secs(j.last_seconds * 1000) : "not run yet";
}

/** How fast SirisAI answers, stage by stage, and its background jobs (7.3, SirisAI 4.6). */
export function SpeedCard() {
  const { data } = useResource("life:speed", () => life.speed(), { refreshMs: 60_000 });
  if (!data) return null;
  const stages = STAGES.filter(([key]) => data.timings.stages[key]);
  const quick = data.timings.recent.filter((t) => t.path === "quick").length;
  const trouble = data.jobs.filter((j) => j.last_error || j.slow);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="SirisAI speed">
      <header className="widget__head"><Gauge aria-hidden="true" /><span>SirisAI speed</span></header>
      {stages.length === 0 ? (
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>No replies timed yet.</p>
      ) : (
        <ul className="items">
          {stages.map(([key, label]) => (
            <li key={key} className="item">
              <span className="item__text">
                <div className="item__title">{label}</div>
                <div className="item__subtitle">Usually {secs(data.timings.stages[key].p50_ms)} · slowest 5% {secs(data.timings.stages[key].p95_ms)}</div>
              </span>
            </li>
          ))}
        </ul>
      )}
      {quick > 0 && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{quick} of the last {data.timings.recent.length} were home commands answered without the model.</p>}
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        {data.jobs.length} background jobs{trouble.length ? `; ${trouble.map((j) => `${j.name.replace(/_/g, " ")} ${jobNote(j)}`).join(", ")}` : ", all fine"}.
      </p>
    </Glass>
  );
}
