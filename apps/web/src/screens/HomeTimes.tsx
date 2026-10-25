import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, RotateCcw } from "lucide-react";
import { DAY_HIDDEN, DAY_WIDGETS, SECTION_ORDER, move, schedule, type DayPhase, type DayTimes, type HomeSchedule } from "../api/home";
import { Sheet } from "../components/Sheet";

const DEFAULT: HomeSchedule = {
  weekday: { morning: "05:00", day: "08:30", evening: "16:30", winddown: "20:00", night: "23:00" },
  weekend: { morning: "05:00", day: "10:00", evening: "17:00", winddown: "20:00", night: "23:00" },
  sections: SECTION_ORDER,
  hidden: DAY_HIDDEN,
  leave_minutes: 30,
};

const PARTS: { phase: DayPhase; label: string }[] = [
  { phase: "morning", label: "Morning" },
  { phase: "work", label: "Work (weekdays)" },
  { phase: "weekend", label: "Weekend daytime" },
  { phase: "evening", label: "Evening" },
  { phase: "winddown", label: "Wind down" },
  { phase: "night", label: "Night" },
];

const TIMES: [keyof DayTimes, string][] = [["morning", "Morning"], ["day", "Work · Daytime"], ["evening", "Evening"], ["winddown", "Wind down"], ["night", "Night"]];

const minutes = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
const inOrder = (t: DayTimes) => TIMES.every(([k], i) => i === 0 || minutes(t[TIMES[i - 1][0]]) < minutes(t[k]));

/** "Times of day" (4.8, 4.9): when each part of the day starts, weekdays and weekends; and for
 *  each part, which Home sections lead and which widgets show. Saved on the server, so every
 *  device follows it. */
export function HomeTimes({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [plan, setPlan] = useState<HomeSchedule | null>(null);
  const [open, setOpen] = useState<DayPhase | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    // A schedule from before wind down (4.8) fills in what it doesn't have.
    schedule.get().then((p) => setPlan({
      ...DEFAULT, ...p,
      weekday: { ...DEFAULT.weekday, ...p.weekday }, weekend: { ...DEFAULT.weekend, ...p.weekend },
      sections: { ...DEFAULT.sections, ...p.sections }, hidden: { ...DEFAULT.hidden, ...p.hidden },
    })).catch(() => setPlan(DEFAULT));
  }, []);

  function setTime(kind: "weekday" | "weekend", key: keyof DayTimes, value: string) {
    if (!plan || !/^\d{2}:\d{2}$/.test(value)) return;
    setPlan({ ...plan, [kind]: { ...plan[kind], [key]: value } });
  }
  function reorder(phase: DayPhase, section: string, by: -1 | 1) {
    if (!plan) return;
    setPlan({ ...plan, sections: { ...plan.sections, [phase]: move(plan.sections[phase], section, by) } });
  }
  function toggle(phase: DayPhase, id: string) {
    if (!plan) return;
    const hidden = plan.hidden[phase] ?? [];
    setPlan({ ...plan, hidden: { ...plan.hidden, [phase]: hidden.includes(id) ? hidden.filter((h) => h !== id) : [...hidden, id] } });
  }
  async function save() {
    if (!plan) return;
    if (!inOrder(plan.weekday) || !inOrder(plan.weekend)) {
      setError("Each part of the day needs to start after the one before it.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await schedule.save(plan);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save that.");
      setSaving(false);
    }
  }

  return (
    <Sheet label="Times of day" onClose={onClose}>
      <header className="sheet__head">
        <h2 className="sheet__title">Times of day</h2>
        <p className="muted" style={{ margin: 0 }}>When each part of the day starts, and what Home shows in it. Every device follows these.</p>
      </header>
      {!plan ? <div className="skeleton" style={{ height: 120 }} /> : (
        <>
          <div className="times__grid" role="group" aria-label="Start times">
            <span />
            <span className="times__head">Weekdays</span>
            <span className="times__head">Weekends</span>
            {TIMES.map(([key, label]) => (
              <TimeRow key={key} label={label} weekday={plan.weekday[key]} weekend={plan.weekend[key]}
                onWeekday={(v) => setTime("weekday", key, v)} onWeekend={(v) => setTime("weekend", key, v)} />
            ))}
          </div>
          <label className="row times__leave">
            <span className="times__label">Leave for places early by</span>
            <input type="number" className="field times__input" min={0} max={180} step={5} value={plan.leave_minutes} aria-label="Minutes before an event to leave"
              onChange={(e) => setPlan({ ...plan, leave_minutes: Math.max(0, Math.min(180, Number(e.target.value) || 0)) })} />
            <span className="muted">min</span>
          </label>
          {PARTS.map(({ phase, label }) => {
            const hidden = plan.hidden[phase] ?? [];
            const showing = DAY_WIDGETS.filter((w) => !hidden.includes(w.id)).length;
            return (
              <section key={phase} className="customise__section" aria-label={`${label} order`}>
                <h3 className="section-title" style={{ marginTop: 14 }}>{label}</h3>
                <ul className="customise__list">
                  {plan.sections[phase].map((section, i, all) => (
                    <li key={section} className="customise__row">
                      <span className="customise__label">{section}</span>
                      <button type="button" className="icon-link" disabled={i === 0} onClick={() => reorder(phase, section, -1)} aria-label={`${label}: move ${section} up`}>
                        <ArrowUp size={16} aria-hidden="true" />
                      </button>
                      <button type="button" className="icon-link" disabled={i === all.length - 1} onClick={() => reorder(phase, section, 1)} aria-label={`${label}: move ${section} down`}>
                        <ArrowDown size={16} aria-hidden="true" />
                      </button>
                    </li>
                  ))}
                </ul>
                <button type="button" className="show-more" aria-expanded={open === phase} onClick={() => setOpen(open === phase ? null : phase)}>
                  {open === phase ? "Done choosing" : `Widgets: ${showing} of ${DAY_WIDGETS.length} showing · choose`}
                </button>
                {open === phase && (
                  <div className="times__widgets" role="group" aria-label={`${label} widgets`}>
                    {DAY_WIDGETS.map((w) => (
                      <label key={w.id} className="times__widget">
                        <input type="checkbox" checked={!hidden.includes(w.id)} onChange={() => toggle(phase, w.id)} aria-label={`${label}: show ${w.label}`} />
                        <span>{w.label}</span>
                      </label>
                    ))}
                  </div>
                )}
              </section>
            );
          })}
          <p className="muted" style={{ margin: "12px 0 0", fontSize: 13 }}>
            Whatever you pick, Home server, Siris apps and Power only show when they need you (the server always on weekends), and the
            car in the evening only when it needs charging. While you're out, Home goes last and protocols are hidden.
          </p>
          {error && <div className="error-banner" role="alert" style={{ marginTop: 10 }}>{error}</div>}
          <div className="row" style={{ justifyContent: "space-between", marginTop: 18 }}>
            <button type="button" className="button button--small" onClick={() => setPlan(DEFAULT)}>
              <RotateCcw size={15} aria-hidden="true" /> Reset
            </button>
            <button type="button" className="button button--small button--primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save"}</button>
          </div>
        </>
      )}
    </Sheet>
  );
}

function TimeRow({ label, weekday, weekend, onWeekday, onWeekend }: {
  label: string; weekday: string; weekend: string; onWeekday: (v: string) => void; onWeekend: (v: string) => void;
}) {
  return (
    <>
      <span className="times__label">{label}</span>
      <input type="time" className="field times__input" value={weekday} onChange={(e) => onWeekday(e.target.value)} aria-label={`${label}, weekdays`} />
      <input type="time" className="field times__input" value={weekend} onChange={(e) => onWeekend(e.target.value)} aria-label={`${label}, weekends`} />
    </>
  );
}
