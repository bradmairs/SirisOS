import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Dumbbell } from "lucide-react";
import { loadActive } from "../api/gym";

/** 7.8: a workout in progress stays one tap away from every page, with how long it's been going. */
export function WorkoutBar() {
  const { pathname } = useLocation();
  const [, tick] = useState(0);
  useEffect(() => { const t = window.setInterval(() => tick((n) => n + 1), 15_000); return () => window.clearInterval(t); }, []);
  if (pathname === "/gym/workout" || pathname === "/gym") return null;  // SirisGym has its own "In progress" card
  const s = loadActive();
  if (!s) return null;
  const min = Math.max(0, Math.floor((Date.now() - new Date(s.started_at).getTime()) / 60000));
  const sets = s.entries.reduce((n, e) => n + e.sets.filter((x) => x.done).length, 0);
  return (
    <Link to="/gym/workout" className="workout-bar" aria-label={`${s.editing ? "Editing" : "Workout in progress"}: ${s.title}. Carry on`}>
      <Dumbbell size={16} aria-hidden="true" />
      <span className="workout-bar__text"><strong>{s.editing ? "Editing" : s.title}</strong>
        <span className="muted">{s.editing ? s.title : `${min} min · ${sets} set${sets === 1 ? "" : "s"}`}</span></span>
      <span className="workout-bar__go">Carry on</span>
    </Link>
  );
}
