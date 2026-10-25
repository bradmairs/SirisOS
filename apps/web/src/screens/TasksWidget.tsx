import { useState } from "react";
import { Link } from "react-router-dom";
import { ListTodo } from "lucide-react";
import { Glass } from "../components/Glass";
import { LoadingWidget } from "../components/WidgetCard";
import { TaskRow, useTasks } from "./Tasks";

/** Home: what's due today (and anything overdue), ticked off in place. `area` keeps it to work
 *  tasks in work hours and personal ones after (4.9). */
export function TasksWidget({ delay = 0, area }: { delay?: number; area?: "work" | "personal" }) {
  const res = useTasks();
  const [note, setNote] = useState<string | null>(null);
  if (!res.data) return res.error ? null : <LoadingWidget title="Tasks" Icon={ListTodo} delay={delay} />;
  const mine = (t: { area?: string }) => !area || !t.area || t.area === area;
  const due = [...res.data.groups.overdue, ...res.data.groups.today].filter(mine);
  const soon = res.data.groups.week.filter(mine).slice(0, 1);
  return (
    <Glass as="section" className="widget" style={{ animationDelay: `${delay}ms` }} aria-label="Tasks">
      <header className="widget__head">
        <ListTodo aria-hidden="true" />
        <span>{area === "work" ? "Work tasks" : area === "personal" ? "Your tasks" : "Tasks"}</span>
        <Link to="/tasks" className="widget__source">{res.data.counts.week + res.data.counts.later + res.data.counts.someday > 0 ? "All tasks" : "Open"}</Link>
      </header>
      {due.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>Nothing due today.{soon[0] ? ` Next: ${soon[0].title}.` : ""}</p>
      ) : (
        <ul className="items">
          {due.slice(0, 4).map((t) => (
            <TaskRow key={t.id} task={t} compact onChanged={(m) => { setNote(m); res.reload(true).catch(() => undefined); }} />
          ))}
        </ul>
      )}
      {due.length > 4 && <Link to="/tasks" className="show-more">and {due.length - 4} more</Link>}
      {note && <p className="tone-good" role="status" style={{ margin: 0, fontSize: 13 }}>{note}</p>}
    </Glass>
  );
}
