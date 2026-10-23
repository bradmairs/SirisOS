import { useState, type FormEvent } from "react";
import { Footprints } from "lucide-react";
import { fitness, type FitnessWeek } from "../api/fitness";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";
import { LoadingWidget } from "../components/WidgetCard";

const DAY = ["M", "T", "W", "T", "F", "S", "S"];

/** This week's running against your goal, from the Health shortcut (3.6). */
export function FitnessWidget({ delay = 0 }: { delay?: number }) {
  const res = useResource<FitnessWeek>("fitness:week", () => fitness.week(), { staleMs: 10 * 60_000, persist: true });
  const [editing, setEditing] = useState(false);
  const [goal, setGoal] = useState("");
  const data = res.data;
  if (!data) return res.error ? null : <LoadingWidget title="Fitness" Icon={Footprints} delay={delay} />;
  if (!data.available) return null;

  const km = data.km ?? 0;
  const pct = data.goal_km ? Math.min(100, (km / data.goal_km) * 100) : null;
  const peak = Math.max(1, ...(data.days ?? []).map((d) => d.km));
  async function save(e: FormEvent) {
    e.preventDefault();
    const value = parseFloat(goal);
    await fitness.setGoal(Number.isFinite(value) && value > 0 ? value : null);
    setEditing(false);
    await res.reload(true);
  }
  return (
    <Glass as="section" className="widget" style={{ animationDelay: `${delay}ms` }} aria-label="Fitness">
      <header className="widget__head">
        <Footprints aria-hidden="true" />
        <span>Fitness</span>
        <button type="button" className="widget__source show-more" style={{ marginTop: 0 }} onClick={() => { setGoal(data.goal_km ? String(data.goal_km) : ""); setEditing(!editing); }}>
          {data.goal_km ? "Goal" : "Set a goal"}
        </button>
      </header>
      <div className="row" style={{ alignItems: "baseline", gap: 10 }}>
        <span className="hud-big">{km}</span>
        <span className="muted" style={{ fontSize: 15 }}>{data.goal_km ? `of ${data.goal_km} km this week` : "km this week"}</span>
      </div>
      {pct !== null && <span className="career-bar" role="presentation"><span className={`career-bar__fill ${pct >= 100 ? "career-bar__fill--good" : ""}`} style={{ width: `${pct}%` }} /></span>}
      <div className="fitness-days" aria-label="Kilometres each day">
        {(data.days ?? []).map((d, i) => (
          <div key={d.date} className={`fitness-day${d.future ? " fitness-day--future" : ""}`} title={`${d.date}: ${d.km} km, ${d.exercise} min`}>
            <span className="fitness-day__bar" style={{ height: `${d.km ? Math.max(10, (d.km / peak) * 100) : 4}%` }} />
            <span className="fitness-day__label">{DAY[i]}</span>
          </div>
        ))}
      </div>
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        {data.runs} run{data.runs === 1 ? "" : "s"} · {data.exercise_minutes} min exercise{data.steps_avg ? ` · ${data.steps_avg.toLocaleString()} steps a day` : ""}
      </p>
      {editing && (
        <form className="row" style={{ gap: 8 }} onSubmit={save}>
          <input className="field" inputMode="decimal" style={{ width: 110 }} value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="km a week" aria-label="Weekly running goal in km" />
          <button type="submit" className="button button--small">Save</button>
        </form>
      )}
    </Glass>
  );
}
