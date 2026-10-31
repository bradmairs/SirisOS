import { Zap } from "lucide-react";
import type { Placements } from "../api/house";
import { sensorRoom, watts, type Power } from "../api/power";
import { FLOORS } from "../house/layout";
import { Glass } from "../components/Glass";
import { useShowMore } from "../components/ShowMore";

/** Power use (5.4): the house now, today's kWh, and each sensor in its room. */
export function PowerCard({ data, error, placements, onRoom }: {
  data: Power | null; error: string | null; placements: Placements; onRoom: (entityId: string, room: string | null) => void;
}) {
  const listed = useShowMore(data?.power ?? [], 6);
  const total = data?.house_watts ?? (data?.power.length ? data.power.reduce((n, s) => n + s.watts, 0) : null);
  return (
    <Glass as="section" className="widget" style={{ minHeight: 0 }} aria-label="Power">
      <header className="widget__head"><Zap aria-hidden="true" /><span>Power</span></header>
      {!data && error && <p className="muted" style={{ margin: 0, fontSize: 14 }}>{error}</p>}
      {data && !data.available && <p className="muted" style={{ margin: 0, fontSize: 14 }}>Power use needs SirisAI 3.11 or later.</p>}
      {data?.available && !data.configured && <p className="muted" style={{ margin: 0, fontSize: 14 }}>Home Assistant isn't set up in SirisAI.</p>}
      {data?.configured && (
        <>
          <div className="metrics">
            <div><div className="metric__value">{watts(total)}</div><div className="metric__label">{data.house_watts != null ? "The house now" : "Sensors now"}</div></div>
            <div><div className="metric__value">{data.today_kwh != null ? `${data.today_kwh.toFixed(1)} kWh` : "–"}</div><div className="metric__label">Today</div></div>
            {data.solar_watts != null && <div><div className="metric__value">{watts(data.solar_watts)}</div><div className="metric__label">Solar</div></div>}
          </div>
          {data.by_device && data.by_device.length > 0 && (
            <>
              <h3 className="maint__h">Today's biggest users</h3>
              <ul className="items" aria-label="Today's biggest users">
                {data.by_device.map((d) => (
                  <li key={d.entity_id} className="item">
                    <span className="item__text"><div className="item__title">{d.name}</div>
                      <div className="item__subtitle">{d.kwh.toFixed(2)} kWh{d.share != null ? ` · ${d.share}% of today` : ""}</div></span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {data.always_on && (
            <p style={{ margin: 0, fontSize: 14 }} aria-label="Always on">
              <strong>Always on: {watts(data.always_on.watts)}</strong> overnight, about {data.always_on.kwh_year.toLocaleString()} kWh a year
              {data.always_on.cost_year != null ? ` (~$${data.always_on.cost_year.toLocaleString()})` : ""}.
              {data.always_on.devices.length > 0 && <> Never off: {data.always_on.devices.map((d) => `${d.name} ${watts(d.watts)}`).join(", ")}.</>}
            </p>
          )}
          {!data.power.length && <p className="muted" style={{ margin: 0, fontSize: 13 }}>No power sensors in Home Assistant yet: smart plugs and a whole-house meter show up here.</p>}
          {data.power.length > 0 && (
            <>
              <p className="muted" style={{ margin: 0, fontSize: 13 }}>Turn on <strong>Power</strong> above to light each room by what it's drawing. A sensor goes in a room by its name; choose another here.</p>
              <ul className="items">
                {listed.shown.map((s) => (
                  <li key={s.entity_id} className="item">
                    <span className={`item__dot ${s.watts > 5 ? "dot-good" : ""}`} aria-hidden="true" />
                    <span className="item__text"><div className="item__title">{s.name}</div><div className="item__subtitle">{watts(s.watts)}</div></span>
                    <select className="field house__room" aria-label={`Room for ${s.name}`} value={sensorRoom(s, placements) ?? ""} onChange={(e) => onRoom(s.entity_id, e.target.value || null)}>
                      <option value="">No room</option>
                      {FLOORS.map((f) => (
                        <optgroup key={f.id} label={`${f.name} floor`}>
                          {f.rooms.filter((r) => !r.id.startsWith("stairs")).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                        </optgroup>
                      ))}
                    </select>
                  </li>
                ))}
              </ul>
              {listed.toggle}
            </>
          )}
        </>
      )}
    </Glass>
  );
}
