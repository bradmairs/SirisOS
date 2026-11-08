import { useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { goals } from "../api/goals";
import { refreshResource, useResource } from "../api/resource";
import { Glass } from "../components/Glass";

/** SirisAI asking on Home (8.3): all January to set the year's goals, all December to review them, until you say it's done. */
export function GoalsPromptCard() {
  const res = useResource("goals:prompt", () => goals.prompt(), { staleMs: 30 * 60_000 });
  const [busy, setBusy] = useState(false);
  const p = res.data?.prompt;
  if (!p) return null;
  const review = p.kind === "review";
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0, marginTop: 14 }} aria-label={review ? `Review your ${p.year} goals` : `Set your ${p.year} goals`}>
      <header className="widget__head"><Sparkles aria-hidden="true" /><span>From SirisAI</span></header>
      <p style={{ margin: 0, fontSize: 16 }}><strong>{review ? `Time to review your ${p.year} goals` : `Time to set your ${p.year} goals`}</strong></p>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>
        {review
          ? `See how ${p.year} went. Anything you didn't finish can carry into ${p.year + 1}.`
          : p.goals ? `You've got ${p.goals} so far. Add any more, then tell me you're done.` : "A few things to aim for this year. Running, CPD, journal and task goals count themselves."}
      </p>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <Link to={review ? `/year?review=${p.year}` : "/year"} className="button button--small button--primary">{review ? "Review them" : "Set them"}</Link>
        {!review && p.goals > 0 && (
          <button type="button" className="button button--small" disabled={busy}
            onClick={async () => { setBusy(true); try { await goals.markSet(p.year); refreshResource(`goals:${p.year}`); await res.reload(true); } finally { setBusy(false); } }}>
            I've set them
          </button>
        )}
      </div>
    </Glass>
  );
}
