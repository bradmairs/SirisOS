import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Compass, Dumbbell } from "lucide-react";
import { gym, loadActive, type Routine } from "../api/gym";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";
import { gymTime } from "../components/Dock";

/** The week's one or two changes (7.0), from SirisAI: training, sleep, recovery and protein together. */
export function GymCoachCard() {
  const res = useResource("gym:coach", () => gym.coach(), { staleMs: 30 * 60_000, persist: true });
  const c = res.data;
  if (!c?.changes?.length) return null;
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="This week's coach">
      <header className="widget__head"><Compass aria-hidden="true" /><span>{c.changes.length === 1 ? "One change this week" : `${c.changes.length} changes this week`}</span></header>
      <ul className="items">
        {c.changes.map((x) => (
          <li key={x.title} className="item"><span className="item__text"><span className="item__title">{x.title}</span><span className="item__subtitle">{x.why}</span></span></li>
        ))}
      </ul>
    </Glass>
  );
}

/** One card from 6 to 8 am (7.0): today's workout, readiness, and one tap to start it and the Watch's Shortcut. */
export function MorningGymCard({ at = new Date() }: { at?: Date }) {
  const navigate = useNavigate();
  const on = gymTime(at);
  const res = useResource("gym:morning", () => gym.morning(), { staleMs: 5 * 60_000, enabled: on });
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const m = res.data;
  if (!on || !m?.plan || m.plan.done || m.plan.rest) return null;
  const going = loadActive();
  const start = async () => {
    setBusy(true);
    setFailed(null);
    try {
      const { startWorkout } = await import("./Gym");
      await startWorkout(navigate, { id: m.routine } as Routine, m.day, m.gym, m.shortcut);
    } catch (e) {
      setFailed(e instanceof Error ? e.message : "Couldn't start it.");
    } finally { setBusy(false); }
  };
  const lifts = m.plan.lifts ?? [];
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0, marginTop: 14 }} aria-label="Today's gym plan">
      <header className="widget__head"><Dumbbell aria-hidden="true" /><span>Gym this morning</span>{m.readiness?.band && <span className="widget__source">Readiness {m.readiness.score ?? ""} · {m.readiness.band}</span>}</header>
      <p style={{ margin: 0, fontSize: 16 }}><strong>{m.plan.title}</strong></p>
      {m.plan.note && <p className="muted" style={{ margin: 0, fontSize: 13 }}>{m.plan.note}</p>}
      {lifts.length > 0 && (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          {lifts.map((l) => `${l.name} ${l.sets} × ${l.reps}${l.weight ? ` at ${l.weight} kg` : ""}`).join(" · ")}{m.plan.more ? ` · and ${m.plan.more} more` : ""}
        </p>
      )}
      {going ? (
        <Link to="/gym/workout" className="button button--primary" style={{ alignSelf: "flex-start" }}>Carry on</Link>
      ) : (
        <button type="button" className="button button--primary" style={{ alignSelf: "flex-start" }} disabled={busy} onClick={start}>{m.shortcut ? "Start it and the Watch" : "Start it"}</button>
      )}
      {failed && <p role="alert" className="tone-warning" style={{ margin: 0, fontSize: 13 }}>{failed}</p>}
    </Glass>
  );
}
