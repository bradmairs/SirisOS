import { useEffect } from "react";
import { usePageContext } from "../api/pageContext";
import { useSearchParams } from "react-router-dom";
import { gym } from "../api/gym";
import { PageHead } from "../components/PageHead";
import { ExercisesView } from "./GymExercises";
import { HistoryView } from "./GymHistory";
import { ProgressView } from "./GymProgress";
import { RoutinesView } from "./GymRoutines";
import { SettingsView } from "./GymSettings";
import { gymSummary, useGym } from "./GymShared";
import { TodayView } from "./GymToday";



// Moved out in 8.9; still importable from here.
export { fmtDay, gymSummary, kg, startWorkout, useGym } from "./GymShared";
export { ExercisePicker, ExerciseSheet } from "./GymExercises";

/** SirisGym (6.5; renamed and given its importer in 6.6): start today's workout, routines, history and the exercises with your records. */
const VIEWS = [{ id: "today", label: "Today" }, { id: "routines", label: "Routines" }, { id: "history", label: "History" }, { id: "progress", label: "Progress" }, { id: "exercises", label: "Exercises" },
  { id: "settings", label: "Settings" }] as const;

type View = (typeof VIEWS)[number]["id"];

export function GymScreen() {
  const res = useGym();
  const [params, setParams] = useSearchParams();
  const view = (VIEWS.find((v) => v.id === params.get("view"))?.id ?? "today") as View;
  useEffect(() => { document.title = "SirisGym · SirisOS"; }, []);
  // Recent workouts get the Watch's verdict (7.1), so what to lift and the rest timer can use it.
  useEffect(() => { gym.refreshEffort().catch(() => {}); }, []);
  const g = res.data;
  usePageContext("SirisGym", g ? gymSummary(g) : null);
  return (
    <>
      <PageHead eyebrow={g ? `${g.total_sessions} workouts · ${g.streak_weeks}-week streak` : "Gym"} title="SirisGym" />
      <div className="row career-views" role="tablist" aria-label="Gym views">
        {VIEWS.map((v) => (
          <button key={v.id} type="button" role="tab" aria-selected={view === v.id} className={`chip chip--button ${view === v.id ? "chip--active" : ""}`}
            onClick={() => setParams(v.id === "today" ? {} : { view: v.id }, { replace: true })}>{v.label}</button>
        ))}
      </div>
      {!g && res.error && <div className="error-banner" role="alert">{res.error}</div>}
      {!g && !res.error && <div className="skeleton" style={{ height: 220, marginTop: 16 }} aria-busy="true" />}
      {g && (
        <div className="stack" style={{ marginTop: 16 }}>
          {view === "today" && <TodayView g={g} onChange={() => res.reload?.(true)} />}
          {view === "routines" && <RoutinesView g={g} onChange={() => res.reload?.(true)} />}
          {view === "history" && <HistoryView g={g} onChange={() => res.reload?.(true)} />}
          {view === "progress" && <ProgressView />}
          {view === "exercises" && <ExercisesView g={g} onChange={() => res.reload?.(true)} />}
          {view === "settings" && <SettingsView g={g} onChange={() => res.reload?.(true)} />}
        </div>
      )}
    </>
  );
}
