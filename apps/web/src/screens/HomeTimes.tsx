import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, RotateCcw } from "lucide-react";
import { move, schedule, type DayPhase, type DayTimes, type HomeSchedule } from "../api/home";
import { Sheet } from "../components/Sheet";

const DEFAULT: HomeSchedule = {
  weekday: { morning: "05:00", day: "08:30", evening: "16:30", night: "23:00" },
  weekend: { morning: "05:00", day: "10:00", evening: "17:00", night: "23:00" },
  sections: {
    morning: ["Now", "Today", "Home"],
    work: ["Today", "Now", "Home"],
    weekend: ["Home", "Today", "Now"],
    evening: ["Today", "Home", "Now"],
    night: ["Today", "Home", "Now"],
  },
};

const PARTS: { phase: DayPhase; label: string }[] = [
  { phase: "morning", label: "Morning" },
  { phase: "work", label: "Work (weekdays)" },
  { phase: "weekend", label: "Weekend daytime" },
  { phase: "evening", label: "Evening" },
  { phase: "night", label: "Night" },
];

const minutes = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5));
const inOrder = (t: DayTimes) => minutes(t.morning) < minutes(t.day) && minutes(t.day) < minutes(t.evening) && minutes(t.evening) < minutes(t.night);

/** "Times of day" (4.8): when each part of the day starts, weekdays and weekends, and which
 *  Home sections lead in each. Saved on the server, so every device follows it. */
export function HomeTimes({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [plan, setPlan] = useState<HomeSchedule | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    schedule.get().then(setPlan).catch(() => setPlan(DEFAULT));
  }, []);

  function setTime(kind: "weekday" | "weekend", key: keyof DayTimes, value: string) {
    if (!plan || !/^\d{2}:\d{2}$/.test(value)) return;
    setPlan({ ...plan, [kind]: { ...plan[kind], [key]: value } });
  }
  function reorder(phase: DayPhase, section: string, by: -1 | 1) {
    if (!plan) return;
    setPlan({ ...plan, sections: { ...plan.sections, [phase]: move(plan.sections[phase], section, by) } });
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
        <p className="muted" style={{ margin: 0 }}>When each part of the day starts, and what Home shows first in it. Every device follows these.</p>
      </header>
      {!plan ? <div className="skeleton" style={{ height: 120 }} /> : (
        <>
          <div className="times__grid" role="group" aria-label="Start times">
            <span />
            <span className="times__head">Weekdays</span>
            <span className="times__head">Weekends</span>
            {([["morning", "Morning"], ["day", "Work · Daytime"], ["evening", "Evening"], ["night", "Night"]] as [keyof DayTimes, string][]).map(([key, label]) => (
              <TimeRow key={key} label={label} weekday={plan.weekday[key]} weekend={plan.weekend[key]}
                onWeekday={(v) => setTime("weekday", key, v)} onWeekend={(v) => setTime("weekend", key, v)} />
            ))}
          </div>
          {PARTS.map(({ phase, label }) => (
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
            </section>
          ))}
          <p className="muted" style={{ margin: "12px 0 0", fontSize: 13 }}>While you're out, Home goes last and protocols are hidden.</p>
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
