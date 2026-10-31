import { useState } from "react";
import { Zap } from "lucide-react";
import { useResource } from "../api/resource";
import { standby, type Standby } from "../api/standby";
import type { Placements } from "../api/house";
import { sensorRoom, watts, type Power } from "../api/power";
import { FLOORS } from "../house/layout";
import { Glass } from "../components/Glass";
import { useShowMore } from "../components/ShowMore";

/** Turn the plug behind an always-on device off overnight and when nobody's home (6.4). */
function StandbySwitches() {
  const res = useResource<Standby>("standby", () => standby.get(), { staleMs: 60_000 });
  const [busy, setBusy] = useState(false);
  const s = res.data;
  if (!s || !s.suggestions.length) return null;
  async function toggle(sw: string, on: boolean) {
    setBusy(true);
    try {
      const next = on ? [...s!.switches, sw] : s!.switches.filter((x) => x !== sw);
      await standby.set(next);
      res.mutate?.({ ...s!, switches: next });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Standby killer">
      <h3 className="maint__h">Off overnight ({s.hours}) and when nobody's home</h3>
      <ul className="items">
        {s.suggestions.map((x) => (
          <li key={x.switch} className="item">
            <label className="row" style={{ gap: 10, fontSize: 14, flex: 1 }}>
              <input type="checkbox" disabled={busy} checked={s.switches.includes(x.switch)} onChange={(e) => toggle(x.switch, e.target.checked)} />
              <span className="item__text"><span className="item__title">{x.name}</span>
                <span className="item__subtitle">{watts(x.watts)} always · {x.switch}{s.off_now.includes(x.switch) ? " · off now" : ""}</span></span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

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
          {data.always_on && data.always_on.devices.length > 0 && <StandbySwitches />}
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
