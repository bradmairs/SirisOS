import { describe, expect, it } from "vitest";
import { powerGlow, roomWatts, sensorRoom, watts, type Power } from "./power";

const p = (sensors: [string, string, number][]): Power => ({ available: true, configured: true, house_watts: null, solar_watts: null, meters: [], today_kwh: null, method: null,
  power: sensors.map(([entity_id, name, w]) => ({ entity_id, name, watts: w })) });

describe("power", () => {
  it("puts sensors in rooms by name or by your choice, and sums each room", () => {
    const data = p([["sensor.dishwasher_power", "Dishwasher power", 1800], ["sensor.tv_plug", "Lounge TV plug", 120], ["sensor.mystery", "Plug 3", 40],
      ["sensor.office_heater", "Heater", 2000]]);
    expect(sensorRoom(data.power[2], {})).toBeNull();
    expect(roomWatts(data, { "sensor.office_heater": { room: "office" } })).toEqual({ kitchen: 1800, lounge: 120, office: 2000 });
    expect(roomWatts(data, { "sensor.dishwasher_power": { room: "office", hidden: true } })).toEqual({ lounge: 120 });
    expect(powerGlow({ office: 2000, lounge: 100 })).toEqual({ office: { color: 0x6fe39a, strength: 1 }, lounge: { color: 0x6fe39a, strength: 0.3 } });
    expect([watts(1250), watts(80), watts(null)]).toEqual(["1.3 kW", "80 W", "–"]);
  });
});
