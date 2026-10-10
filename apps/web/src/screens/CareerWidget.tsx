import { Link } from "react-router-dom";
import { Award } from "lucide-react";
import { career, type CareerOverview } from "../api/career";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

/** Home: CPD in the last 3 years and the next career step (ADR 111). */
export function CareerWidget({ delay = 0 }: { delay?: number }) {
  const { data } = useResource<CareerOverview>("career:overview", () => career.overview(), { staleMs: 60_000 });
  if (!data) return null;
  const cpd = data.cpd;
  const next = data.next_steps[0];
  const pct = Math.min(100, (cpd.total / cpd.required) * 100);
  return (
    <Glass as="section" className="widget" style={{ animationDelay: `${delay}ms` }} aria-label="Career">
      <header className="widget__head">
        <Award aria-hidden="true" />
        <span>Career</span>
        <Link to="/career" className="widget__source">Open</Link>
      </header>
      {cpd.records ? (
        <>
          <div className="row" style={{ alignItems: "baseline", gap: 10 }}>
            <span className="hud-big">{Math.round(cpd.total)}</span>
            <span className="muted" style={{ fontSize: 15 }}>of {cpd.required} CPD hours</span>
          </div>
          <span className="career-bar" role="presentation">
            <span className={`career-bar__fill ${cpd.met ? "career-bar__fill--good" : ""}`} style={{ width: `${pct}%` }} />
          </span>
        </>
      ) : (
        <p className="muted" style={{ margin: 0 }}>Import your CPD from Engineers Australia to track your hours.</p>
      )}
      {next && (
        <p className="muted" style={{ margin: 0 }}>
          Next: <span style={{ color: "var(--ink)" }}>{next.title}</span> · {next.detail}
        </p>
      )}
    </Glass>
  );
}
