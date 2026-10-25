import { useEffect, useState, type FormEvent } from "react";
import { AlarmClock, BrainCircuit, Briefcase, Check, Circle, House, ListTodo, Plus, Repeat2, Sparkles, Trash2 } from "lucide-react";
import { useResource } from "../api/resource";
import { dueLabel, GROUP_LABEL, tasks, type TaskGroup, type TaskItem, type TaskList } from "../api/tasks";
import { Glass } from "../components/Glass";
import { useShowMore } from "../components/ShowMore";

const ORDER: TaskGroup[] = ["overdue", "today", "week", "later", "someday"];
const SOURCE_ICON = { sirisos: ListTodo, siris: BrainCircuit, reminder: Sparkles } as const;
const SOURCE_LABEL = { sirisos: "Task", siris: "Siris", reminder: "SirisAI reminder" } as const;

export function useTasks() {
  return useResource<TaskList>("tasks:list", () => tasks.list(), { staleMs: 30_000, persist: true });
}

/** One task: tick it, push it to later, or (for SirisOS's own) delete it. */
export function TaskRow({ task, onChanged, compact }: { task: TaskItem; onChanged: (message: string) => void; compact?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [snoozing, setSnoozing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const Icon = SOURCE_ICON[task.source];

  async function run(fn: () => Promise<string>) {
    setBusy(true);
    setError(null);
    try {
      onChanged(await fn());
    } catch (err) {
      setError(err instanceof Error ? err.message : "That didn't work.");
    } finally {
      setBusy(false);
      setSnoozing(false);
    }
  }

  const sub = [dueLabel(task), task.source === "siris" ? task.detail : task.source === "reminder" ? "SirisAI reminder" : task.detail].filter(Boolean).join(" · ");
  return (
    <li className={`item task${task.group === "overdue" ? " task--late" : ""}`}>
      <button type="button" className="task__tick" disabled={busy} aria-label={`Done: ${task.title}`}
        onClick={() => run(async () => {
          const r = await tasks.done(task);
          return r.action === "repeated" ? `“${task.title}” is next due ${dueLabel({ due: r.next_due ?? null, time: null, group: "later" })}` : `Done: ${task.title}`;
        })}>
        {busy ? <Check size={18} aria-hidden="true" /> : <Circle size={18} aria-hidden="true" />}
      </button>
      <span className="item__text">
        <div className="item__title">{task.title}</div>
        {(sub || !compact) && (
          <div className="item__subtitle task__sub">
            <Icon size={12} aria-label={SOURCE_LABEL[task.source]} />
            {task.repeat !== "none" && <Repeat2 size={12} aria-label={`Repeats ${task.repeat}`} />}
            <span>{sub || SOURCE_LABEL[task.source]}</span>
          </div>
        )}
        {error && <div className="tone-critical" style={{ fontSize: 13 }}>{error}</div>}
      </span>
      {snoozing ? (
        <span className="task__snooze" role="group" aria-label={`Snooze ${task.title}`}>
          {([["tomorrow", "Tomorrow"], ["weekend", "Weekend"], ["next-week", "Next week"]] as const).map(([until, label]) => (
            <button key={until} type="button" className="chip chip--button" disabled={busy}
              onClick={() => run(async () => { await tasks.snooze(task.id, until); return `Snoozed “${task.title}” to ${label.toLowerCase()}`; })}>
              {label}
            </button>
          ))}
        </span>
      ) : (
        <span className="suggest__actions">
          <button type="button" className="icon-link" disabled={busy} onClick={() => setSnoozing(true)} aria-label={`Snooze ${task.title}`} title="Later">
            <AlarmClock size={15} aria-hidden="true" />
          </button>
          {task.source === "sirisos" && !compact && task.area && (
            <button type="button" className={`chip chip--button task__area${task.area_set ? "" : " task__area--guess"}`} disabled={busy}
              aria-label={`${task.title}: ${task.area}${task.area_set ? "" : " (a guess)"}. Make it ${task.area === "work" ? "personal" : "work"}`}
              title={task.area_set ? "Tap to change" : "Guessed from its words: tap to change"}
              onClick={() => run(async () => {
                const next = task.area === "work" ? "personal" : "work";
                await tasks.update(task.id, { area: next });
                return `“${task.title}” is ${next} now`;
              })}>
              {task.area === "work" ? <Briefcase size={12} aria-hidden="true" /> : <House size={12} aria-hidden="true" />} {task.area === "work" ? "Work" : "Personal"}
            </button>
          )}
          {task.source === "sirisos" && !compact && (
            <button type="button" className="icon-link" disabled={busy} aria-label={`Delete ${task.title}`} title="Delete"
              onClick={() => run(async () => { await tasks.remove(task.id); return `Deleted “${task.title}”`; })}>
              <Trash2 size={15} aria-hidden="true" />
            </button>
          )}
        </span>
      )}
    </li>
  );
}

function Group({ group, items, onChanged }: { group: TaskGroup; items: TaskItem[]; onChanged: (m: string) => void }) {
  const { shown, toggle } = useShowMore(items, group === "someday" || group === "later" ? 5 : 12);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label={GROUP_LABEL[group]}>
      <header className="widget__head">
        <span className={group === "overdue" ? "tone-critical" : undefined}>{GROUP_LABEL[group]}</span>
        <span className="widget__source">{items.length}</span>
      </header>
      <ul className="items">{shown.map((t) => <TaskRow key={t.id} task={t} onChanged={onChanged} />)}</ul>
      {toggle}
    </Glass>
  );
}

/** The few things to get done (2.9; only SirisOS's own since 4.4, not Siris notes or reminders). */
export function TasksScreen() {
  const res = useTasks();
  const data = res.data ?? null;
  const [text, setText] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    document.title = "Tasks · SirisOS";
  }, []);

  const changed = (message: string) => {
    setNote(message);
    res.reload(true).catch(() => undefined);
  };

  async function add(e: FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setAdding(true);
    setError(null);
    try {
      const made = await tasks.add({ text: text.trim() });
      setText("");
      changed(`Added “${made.title}”${made.due ? `, ${dueLabel({ due: made.due, time: made.time, group: "later" })}` : ""}${made.repeat !== "none" ? `, repeats ${made.repeat}` : ""}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add it.");
    } finally {
      setAdding(false);
    }
  }

  const today = data ? data.counts.overdue + data.counts.today : null;
  return (
    <>
      <header className="page-head">
        <div>
          <p className="page-head__eyebrow">{today === null ? "Loading…" : today === 0 ? "Nothing due today" : `${today} for today`}</p>
          <h1 className="page-head__title">Tasks</h1>
        </div>
      </header>
      <Glass as="form" shape="pill" className="ask-bar" onSubmit={add} style={{ marginTop: 16 }}>
        <Plus aria-hidden="true" />
        <input className="ask-bar__input" placeholder="Add a task, like “pay rego Friday”" value={text}
          onChange={(e) => setText(e.target.value)} aria-label="Add a task" />
        <button type="submit" className="button button--small button--primary" disabled={adding || !text.trim()}>{adding ? "Adding…" : "Add"}</button>
      </Glass>
      {note && <p className="tone-good suggest__done" role="status" style={{ marginTop: 10 }}><Check size={14} aria-hidden="true" /> {note}</p>}
      {error && <p className="tone-critical" role="alert">{error}</p>}
      <div className="stack" style={{ marginTop: 14 }}>
        {!data && !res.error && <div className="skeleton" style={{ height: 160 }} aria-label="Loading tasks" />}
        {!data && res.error && <p className="tone-critical">{res.error}</p>}
        {data && ORDER.every((g) => data.counts[g] === 0) && <p className="muted">No tasks. Add one above, or say “remind me to…” in quick capture.</p>}
        {data && ORDER.filter((g) => data.counts[g] > 0).map((g) => <Group key={g} group={g} items={data.groups[g]} onChanged={changed} />)}
      </div>
    </>
  );
}
