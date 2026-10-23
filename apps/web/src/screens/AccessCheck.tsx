import { useState } from "react";
import { CheckCircle2, CircleSlash, Radar, TriangleAlert, XCircle } from "lucide-react";
import { runAccessCheck, type Check } from "../api/access";
import { Glass } from "../components/Glass";

const ICON = { good: CheckCircle2, warn: TriangleAlert, bad: XCircle, skip: CircleSlash };
const TONE = { good: "tone-good", warn: "tone-warning", bad: "tone-critical", skip: "muted" };

/** Is SirisOS working from where you are? Run it at work, on mobile data, on the VPN (3.9). */
export function AccessCheckCard() {
  const [checks, setChecks] = useState<Check[]>([]);
  const [running, setRunning] = useState(false);
  const [ran, setRan] = useState(false);

  async function run() {
    setChecks([]);
    setRunning(true);
    await runAccessCheck((c) => setChecks((list) => [...list.filter((x) => x.id !== c.id), c])).catch(() => undefined);
    setRunning(false);
    setRan(true);
  }

  const bad = checks.filter((c) => c.state === "bad").length;
  const warn = checks.filter((c) => c.state === "warn").length;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Access from here">
      <header className="widget__head"><Radar aria-hidden="true" /><span>Access from here</span>
        <button type="button" className="button button--small" style={{ marginLeft: "auto" }} disabled={running} onClick={run}>
          {running ? "Checking…" : ran ? "Check again" : "Check from here"}
        </button>
      </header>
      {!ran && !running && (
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>
          Run this at work, on mobile data or on the VPN: it tests SirisOS the way this phone sees it, including notifications, live updates and the terminal.
        </p>
      )}
      {ran && (
        <p className={bad ? "tone-critical" : warn ? "tone-warning" : "tone-good"} role="status" style={{ margin: 0, fontWeight: 600 }}>
          {bad ? `${bad} thing${bad === 1 ? "" : "s"} won't work from here` : warn ? `Works, with ${warn} thing${warn === 1 ? "" : "s"} to look at` : "Everything works from here"}
        </p>
      )}
      {checks.length > 0 && (
        <ul className="items">
          {checks.map((c) => {
            const Icon = ICON[c.state];
            return (
              <li key={c.id} className="item">
                <Icon size={16} className={TONE[c.state]} aria-label={c.state} />
                <span className="item__text">
                  <div className="item__title">{c.name}</div>
                  <div className="item__subtitle">{c.detail}</div>
                  {c.fix && <div className="item__subtitle" style={{ color: "var(--ink)" }}>{c.fix}</div>}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </Glass>
  );
}
