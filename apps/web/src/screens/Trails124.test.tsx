import { describe, expect, it, vi } from "vitest";

vi.mock("leaflet", () => ({ default: {} }));
vi.mock("leaflet/dist/leaflet.css", () => ({}));

import { weatherLine } from "./Trails";

describe("SirisTrails 12.4", () => {
  it("puts the weather on a walk in one line, leaving out what doesn't matter", () => {
    const base = { temp_c: 13.2, temp_min_c: 13.1, temp_max_c: 13.4, feels_c: 11.1, rain_mm: 1.2, wind_kmh: 11.7, gust_kmh: 24, humidity: 84, code: 53, sky: "Drizzle", icon: "🌦️" };
    expect(weatherLine(base)).toBe("🌦️ Drizzle · 13°C · feels 11° · 1.2 mm rain · wind 12 km/h, gusts 24 · 84% humidity");
    expect(weatherLine({ ...base, temp_min_c: 18, temp_max_c: 24, feels_c: 13.5, rain_mm: 0, gust_kmh: null, humidity: null }))
      .toBe("🌦️ Drizzle · 18–24°C · wind 12 km/h");
  });
});
