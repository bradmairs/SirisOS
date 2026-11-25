import { Link } from "react-router-dom";
import { Check, Repeat } from "lucide-react";
import { mind, type Habit } from "../api/mind";
import { useResource } from "../api/resource";
import { Glass } from "../components/Glass";

/** Today's habits on Home (9.4): one tap to tick, and a streak at risk says so from the evening. Nothing when you have none.
 * 11.8.0: Wrap Up has them too (`wrapup`), so the day's habits get ticked as you close it. */
export function HabitsHomeWidget({ wrapup = false }: { wrapup?: boolean } = {}) {
  const res = useResource<{ habits: Habit[] }>("mind:habits", () => mind.habits(), { staleMs: 60_000, persist: true });
  // 9.8: only today's habits (one for weekdays doesn't show on a Saturday), and any already ticked.
  const habits = (res.data?.habits ?? []).filter((h) => h.due_today !== false || h.today);
  if (!habits.length) return null;
  const evening = wrapup || new Date().getHours() >= 18;
  const done = habits.filter((h) => h.today).length;
  const tick = async (h: Habit) => { try { res.mutate?.(await mind.markHabit(h.id, !h.today)); } catch { /* it stays as it was */ } };
  return (
    <Glass as="section" className="widget" style={wrapup ? { minHeight: 0 } : undefined} aria-label={wrapup ? "Today's habits" : "Habits"}>
      <header className="widget__head"><Repeat aria-hidden="true" /><span>{wrapup ? "Today's habits" : "Habits"}</span><Link to="/health?view=habits" className="widget__source">{done}/{habits.length} today</Link></header>
      {wrapup && (
        <p className={done === habits.length ? "tone-good" : "muted"} style={{ margin: 0, fontSize: 14 }}>
          {done === habits.length ? "All done today." : "Tick the ones you did today."}
        </p>
      )}
      <ul className="items">
        {habits.map((h) => {
          const risk = evening && !h.today && h.streak > 0;
          return (
            <li key={h.id} className="item">
              <button type="button" className={`gym-sets__done ${h.today ? "gym-sets__done--on" : ""}`} aria-pressed={h.today} aria-label={`${h.name}: done today`} onClick={() => tick(h)}>
                <Check size={16} aria-hidden="true" /></button>
              <span className="item__text">
                <span className="item__title">{h.name}</span>
                <span className={`item__subtitle ${risk ? "tone-warning" : ""}`}>{risk ? `Keep your ${h.streak}-day streak` : h.streak ? `${h.streak}-day streak` : "Start a streak"}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </Glass>
  );
}
