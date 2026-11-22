import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Compass, Lightbulb, ListChecks, Target } from "lucide-react";
import { Glass } from "../components/Glass";
import { useResource } from "../api/resource";
import { away, patterns, plan, steer, type Away, type DayPlan, type Patterns, type SteerGoal } from "../api/assist";

/** 11.3: the day's plan, while you were away, patterns across sections, and goals off pace. */

const ampm = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number);
  return `${h % 12 || 12}${m ? `:${String(m).padStart(2, "0")}` : ""}${h < 12 ? "am" : "pm"}`;
};
const KIND: Record<string, string> = { deep: "Focus", quick: "Quick", normal: "", errand: "Errands", set: "At its time", goal: "Goal" };

/** Today's tasks fitted into the calendar's free time; worked out again whenever it's looked at. */
export function PlanCard() {
  const res = useResource<DayPlan>("assist:plan", () => plan.today(), { staleMs: 5 * 60_000, refreshMs: 10 * 60_000 });
  const p = res.data;
  if (!p || !Array.isArray(p.blocks) || (p.blocks.length === 0 && (!Array.isArray(p.left) || p.left.length === 0))) return null;
  const nowHm = new Date().toTimeString().slice(0, 5);
  const next = p.blocks.filter((b) => b.end > nowHm).slice(0, 5);
  if (!next.length && !p.left.length) return null;
  return (
    <Glass as="section" className="widget" aria-label="Your plan for today">
      <header className="widget__head"><ListChecks aria-hidden="true" /><span>Your plan for today</span>
        <Link to="/tasks" className="widget__source">Tasks</Link></header>
      <ul className="items">
        {next.map((b) => (
          <li key={`${b.start}${b.title}`} className="item">
            <span className="item__text"><span className="item__title">{b.title}</span>
              <span className="item__subtitle">{ampm(b.start)}–{ampm(b.end)}{KIND[b.kind] ? ` · ${KIND[b.kind]}` : ""}{b.goal ? ` · for ${b.goal}` : ""}</span></span>
          </li>
        ))}
      </ul>
      {p.left.length > 0 && <p className="muted" style={{ margin: 0, fontSize: 12 }}>{p.left.length} won't fit today: {p.left.slice(0, 2).map((l) => l.title).join(", ")}{p.left.length > 2 ? "…" : ""}. {p.left[0].why}</p>}
      {p.readiness != null && p.readiness < 40 && <p className="muted" style={{ margin: 0, fontSize: 12 }}>Readiness is low, so it's a lighter plan.</p>}
    </Glass>
  );
}

/** After 20 hours or more away: what changed and what's waiting. "Got it" marks it all seen. */
export function AwayCard() {
  const [a, setA] = useState<Away | null>(null);
  const asked = useRef(false);
  useEffect(() => {
    if (asked.current) return;
    asked.current = true;
    away.get().then((r) => {
      if (r?.away && Array.isArray(r.items)) setA(r);
      else away.touch().catch(() => undefined);
    }).catch(() => undefined);
  }, []);
  if (!a || !a.items || a.items.length === 0) return null;
  return (
    <Glass as="section" className="widget widget--wide" aria-label="While you were away">
      <header className="widget__head"><Compass aria-hidden="true" /><span>While you were away</span><span className="widget__source">{a.away_for}</span></header>
      <ul className="items">
        {a.items.map((i) => (
          <li key={i.kind + i.title} className="item">
            <span className="item__text"><Link to={i.url} className="item__title" style={{ color: "inherit" }}>{i.title}</Link>
              {i.lines.length > 0 && <span className="item__subtitle">{i.lines.join(" · ")}</span>}</span>
          </li>
        ))}
      </ul>
      <button type="button" className="button button--small button--primary" style={{ alignSelf: "flex-start" }}
        onClick={async () => { await away.done(a.keys ?? []).catch(() => undefined); setA(null); }}>Got it</button>
    </Glass>
  );
}

/** Patterns across sections that keep up over weeks, the strongest two. */
export function PatternsCard() {
  const res = useResource<Patterns>("assist:patterns", () => patterns.get(), { staleMs: 6 * 60 * 60_000, persist: true });
  const list = Array.isArray(res.data?.patterns) ? res.data!.patterns.slice(0, 2) : [];
  if (!list.length) return null;
  return (
    <Glass as="section" className="widget" aria-label="Patterns in your days">
      <header className="widget__head"><Lightbulb aria-hidden="true" /><span>Patterns in your days</span><span className="widget__source">{res.data!.days} days</span></header>
      <ul className="stack" style={{ gap: 10, margin: 0, padding: 0, listStyle: "none" }}>
        {list.map((p) => (
          <li key={p.id} style={{ fontSize: 14 }}>{p.text}{p.try && <span className="muted"> {p.try}</span>}</li>
        ))}
      </ul>
    </Glass>
  );
}

const fmt = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: n < 10 ? 1 : 0 });

/** The goals that are behind, with their pace and this week's step (Home), or every goal's pace (Your year). */
export function GoalsPaceCard({ all = false }: { all?: boolean }) {
  const res = useResource("assist:steer", () => steer.get(), { staleMs: 60 * 60_000, persist: true });
  const d = res.data;
  const goals: SteerGoal[] = !d || !Array.isArray(d.goals) ? [] : all ? d.goals.filter((g) => g.projected != null || g.step) : d.behind;
  if (!goals.length) return null;
  return (
    <Glass as="section" className="widget" aria-label={all ? "Goals: pace" : "Goals off pace"}>
      <header className="widget__head"><Target aria-hidden="true" /><span>{all ? "Pace" : "Goals off pace"}</span>
        {!all && <Link to="/year" className="widget__source">Your year</Link>}</header>
      <ul className="items">
        {goals.map((g) => (
          <li key={g.id} className="item">
            <span className="item__text"><span className="item__title">{g.title}</span>
              <span className="item__subtitle" style={{ whiteSpace: "normal" }}>
                {g.projected != null && g.target ? `On pace for ${fmt(g.projected)} of ${fmt(g.target)}${g.unit ? ` ${g.unit}` : ""}` : ""}
                {g.step ? `${g.projected != null ? ". " : ""}${g.step.text}` : ""}
              </span></span>
          </li>
        ))}
      </ul>
    </Glass>
  );
}
