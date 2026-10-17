import { ArrowDown, ArrowUp, Eye, EyeOff, RotateCcw } from "lucide-react";
import type { DeviceLayout } from "../api/home";
import { move } from "../api/home";
import { Sheet } from "../components/Sheet";

export interface SlotInfo {
  id: string;
  label: string;
}

export interface SectionInfo {
  title: string;
  /** In their current (arranged) order, hidden ones included. */
  slots: SlotInfo[];
}

/** "Customise Home": reorder and show/hide widgets for this kind of device. */
export function HomeCustomise({ device, sections, layout, onChange, onClose }: {
  device: "phone" | "desktop";
  sections: SectionInfo[];
  layout: DeviceLayout;
  onChange: (layout: DeviceLayout) => void;
  onClose: () => void;
}) {
  const hidden = new Set(layout.hidden);
  // The saved order is every section's ids in its current order.
  const allIds = sections.flatMap((s) => s.slots.map((slot) => slot.id));

  function reorder(section: SectionInfo, id: string, by: -1 | 1) {
    const moved = move(section.slots.map((s) => s.id), id, by);
    const order = sections.flatMap((s) => (s === section ? moved : s.slots.map((slot) => slot.id)));
    onChange({ ...layout, order });
  }
  function toggle(id: string) {
    const next = hidden.has(id) ? layout.hidden.filter((h) => h !== id) : [...layout.hidden, id];
    onChange({ order: layout.order.length ? layout.order : allIds, hidden: next });
  }

  return (
    <Sheet label="Customise Home" onClose={onClose}>
      <header className="sheet__head">
        <h2 className="sheet__title">Customise Home</h2>
        <p className="muted" style={{ margin: 0 }}>
          Your {device} layout. {device === "phone" ? "Desktop" : "Phone"} keeps its own.
        </p>
      </header>
      {sections.map((section) => (
        <section key={section.title} className="customise__section" aria-label={section.title}>
          <h3 className="section-title" style={{ marginTop: 14 }}>{section.title}</h3>
          <ul className="customise__list">
            {section.slots.map((slot, i) => {
              const off = hidden.has(slot.id);
              return (
                <li key={slot.id} className={`customise__row ${off ? "customise__row--off" : ""}`}>
                  <span className="customise__label">{slot.label}</span>
                  <button type="button" className="icon-link" disabled={i === 0} onClick={() => reorder(section, slot.id, -1)} aria-label={`Move ${slot.label} up`}>
                    <ArrowUp size={16} aria-hidden="true" />
                  </button>
                  <button type="button" className="icon-link" disabled={i === section.slots.length - 1} onClick={() => reorder(section, slot.id, 1)} aria-label={`Move ${slot.label} down`}>
                    <ArrowDown size={16} aria-hidden="true" />
                  </button>
                  <button type="button" className="icon-link" onClick={() => toggle(slot.id)} aria-pressed={!off} aria-label={`${off ? "Show" : "Hide"} ${slot.label}`}>
                    {off ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
      <div className="row" style={{ justifyContent: "space-between", marginTop: 18 }}>
        <button type="button" className="button button--small" onClick={() => onChange({ order: [], hidden: [] })}>
          <RotateCcw size={15} aria-hidden="true" /> Reset
        </button>
        <button type="button" className="button button--small button--primary" onClick={onClose}>Done</button>
      </div>
    </Sheet>
  );
}
