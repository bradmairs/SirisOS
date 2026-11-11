import { CalendarClock, Cake, CheckSquare, Plane, Receipt } from "lucide-react";
import type { ReactNode } from "react";
import { useResource } from "../api/resource";
import { life, people } from "../api/life";
import { tasks } from "../api/tasks";
import { Glass } from "../components/Glass";

export interface Entry { key: string; time: string | null; text: string; kind: "event" | "task" | "bill" | "birthday" | "trip"; sub?: string }

const ICON: Record<Entry["kind"], typeof CalendarClock> = { event: CalendarClock, task: CheckSquare, bill: Receipt, birthday: Cake, trip: Plane };
const pad = (n: number) => String(n).padStart(2, "0");
const ymd = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

/** Everything about today in one list (7.7): the calendar and tasks by time,
 * then what's coming in the next few days (bills, birthdays, a trip). */
export function buildDay(now: Date, src: {
  events?: { summary: string; start: string }[]; tasks?: { id: string; title: string; due: string | null; time: string | null; group: string }[];
  bills?: { id: number; label: string; due_date: string | null }[]; people?: { id: number; name: string; days_to_birthday?: number; turning?: number | null }[];
  trips?: { key: string; destination: string; start: string; nights: number }[];
}): { timed: Entry[]; anytime: Entry[]; soon: Entry[] } {
  const today = ymd(now);
  const timed: Entry[] = [], anytime: Entry[] = [], soon: Entry[] = [];
  for (const e of src.events ?? []) {
    const start = new Date(e.start);
    if (ymd(start) !== today) continue;
    const allDay = e.start.length <= 10;
    (allDay ? anytime : timed).push({ key: `e:${e.summary}:${e.start}`, kind: "event", text: e.summary, time: allDay ? null : `${pad(start.getHours())}:${pad(start.getMinutes())}` });
  }
  for (const t of src.tasks ?? []) {
    if (t.group !== "today" && t.group !== "overdue") continue;
    (t.time ? timed : anytime).push({ key: `t:${t.id}`, kind: "task", text: t.title, time: t.time, sub: t.group === "overdue" ? "overdue" : undefined });
  }
  const horizon = ymd(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 3));
  for (const b of src.bills ?? []) {
    if (b.due_date && b.due_date >= today && b.due_date <= horizon) soon.push({ key: `b:${b.id}`, kind: "bill", text: b.label, time: null, sub: b.due_date === today ? "today" : undefined });
  }
  for (const p of src.people ?? []) {
    if (p.days_to_birthday != null && p.days_to_birthday <= 7) {
      soon.push({ key: `p:${p.id}`, kind: "birthday", time: null, text: `${p.name}'s birthday ${p.days_to_birthday === 0 ? "today" : `in ${p.days_to_birthday} day${p.days_to_birthday === 1 ? "" : "s"}`}${p.turning ? ` (${p.turning})` : ""}` });
    }
  }
  for (const t of src.trips ?? []) {
    const days = Math.round((new Date(t.start.slice(0, 10) + "T00:00:00").getTime() - new Date(today + "T00:00:00").getTime()) / 86_400_000);
    if (days >= 0 && days <= 14) soon.push({ key: `trip:${t.key}`, kind: "trip", time: null, text: days === 0 ? `Off to ${t.destination} today` : `${t.destination} in ${days} day${days === 1 ? "" : "s"}`, sub: t.nights ? `${t.nights} nights` : undefined });
  }
  timed.sort((a, b) => (a.time ?? "").localeCompare(b.time ?? ""));
  return { timed, anytime, soon };
}

function Row({ entry, past }: { entry: Entry; past?: boolean }) {
  const Icon = ICON[entry.kind];
  return (
    <li className={`timeline__row${past ? " timeline__row--past" : ""}`}>
      <span className="timeline__time">{entry.time ?? ""}</span>
      <span className="timeline__dot" aria-hidden="true"><Icon size={14} /></span>
      <span className="timeline__text">{entry.text}{entry.sub && <span className="muted"> · {entry.sub}</span>}</span>
    </li>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (<><li className="timeline__group">{title}</li>{children}</>);
}

export function TodayTimeline({ events }: { events?: { summary: string; start: string }[] }) {
  const { data } = useResource("home:today", async () => {
    const [t, b, p, tr] = await Promise.allSettled([tasks.list(), life.bills(), people.list(), life.travel()]);
    const ok = <T,>(r: PromiseSettledResult<T>) => (r.status === "fulfilled" ? r.value : undefined);
    const list = ok(t);
    return {
      tasks: list ? [...list.groups.overdue, ...list.groups.today] : [],
      bills: ok(b) ?? [], people: ok(p) ?? [], trips: ok(tr) ?? [],
    };
  }, { refreshMs: 5 * 60_000, persist: true });
  const now = new Date();
  const day = buildDay(now, { events, ...data });
  const nowHm = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  const empty = !day.timed.length && !day.anytime.length && !day.soon.length;
  return (
    <Glass as="section" className="widget timeline" aria-label="Today">
      <header className="widget__head"><CalendarClock aria-hidden="true" /><span>Today</span>
        <span className="widget__source">{now.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}</span>
      </header>
      {empty ? <p className="muted" style={{ margin: 0 }}>{data ? "Nothing in the calendar or on your list today." : "Loading…"}</p> : (
        <ul className="timeline__list">
          {day.timed.map((e) => <Row key={e.key} entry={e} past={(e.time ?? "") < nowHm} />)}
          {day.anytime.length > 0 && <Group title="Any time today">{day.anytime.map((e) => <Row key={e.key} entry={e} />)}</Group>}
          {day.soon.length > 0 && <Group title="Coming up">{day.soon.map((e) => <Row key={e.key} entry={e} />)}</Group>}
        </ul>
      )}
    </Glass>
  );
}
