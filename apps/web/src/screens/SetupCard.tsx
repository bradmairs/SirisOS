import { useState } from "react";
import { Link } from "react-router-dom";
import { CircleAlert, CircleCheck, CircleDashed, ListChecks, RefreshCw } from "lucide-react";
import { setup, type Setup, type SetupItem } from "../api/setup";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

const ICON = { on: CircleCheck, off: CircleDashed, problem: CircleAlert };
const TONE = { on: "tone-good", off: "muted", problem: "tone-critical" };
const LABEL = { on: "On", off: "Not set up", problem: "Needs a look" };

/** The setup checklist (5.6): what's switched on, tested live, and how to switch on the rest. */
export function SetupCard() {
  const res = useResource<Setup>("setup", () => setup.get(), { staleMs: 5 * 60_000, persist: true });
  const [showOn, setShowOn] = useState(false);
  const data = res.data;
  const order = (i: SetupItem) => ({ problem: 0, off: 1, on: 2 })[i.state];
  const items = [...(data?.items ?? [])].sort((a, b) => order(a) - order(b));
  const shown = showOn ? items : items.filter((i) => i.state !== "on");
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Setup">
      <header className="widget__head"><ListChecks aria-hidden="true" /><span>Setup</span>
        <button type="button" className="widget__source icon-link" aria-label="Check again" onClick={() => res.reload(true).catch(() => undefined)}>
          <RefreshCw size={14} className={res.loading ? "spin" : ""} aria-hidden="true" />
        </button></header>
      {!data && res.error && <p className="muted" style={{ margin: 0 }}>{res.error}</p>}
      {data && (
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>
          {data.counts.on} on · {data.counts.off} not set up · {data.counts.problem} need{data.counts.problem === 1 ? "s" : ""} a look
        </p>
      )}
      <ul className="items setup__items">
        {shown.map((i) => {
          const Icon = ICON[i.state];
          return (
            <li key={i.id} className="item setup__item">
              <Icon size={18} className={TONE[i.state]} aria-label={LABEL[i.state]} />
              <span className="item__text">
                <span className="item__title career-wrap">{i.link ? <Link to={i.link}>{i.title}</Link> : i.title} <span className="muted setup__area">{i.area}</span></span>
                <span className="item__subtitle career-wrap">{i.detail}</span>
                {i.fix && i.state !== "on" && <span className="setup__fix career-wrap">{i.fix}</span>}
                {i.settings.length > 0 && i.state !== "on" && <span className="setup__settings">{i.settings.map((s) => <code key={s}>{s}</code>)}</span>}
              </span>
            </li>
          );
        })}
      </ul>
      {data && data.counts.on > 0 && (
        <button type="button" className="show-more" aria-expanded={showOn} onClick={() => setShowOn((x) => !x)}>
          {showOn ? "Hide what's on" : `Show the ${data.counts.on} that are on`}
        </button>
      )}
    </Glass>
  );
}
