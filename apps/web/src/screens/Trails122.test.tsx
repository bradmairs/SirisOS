import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

// jsdom can't draw a map: Leaflet is replaced by something that records what's drawn.
const drawn: { lines: number } = { lines: 0 };
vi.mock("leaflet", () => {
  const chain = (): Record<string, unknown> => ({ addTo: () => chain(), bindTooltip: () => chain(), on: () => chain(), getBounds: () => ({ isValid: () => true }),
    setLatLng: () => chain(), setStyle: () => chain() });
  const L = {
    map: () => ({ fitBounds: vi.fn(), setView: vi.fn(), invalidateSize: vi.fn(), remove: vi.fn() }),
    tileLayer: () => chain(), control: { layers: () => chain() }, layerGroup: () => ({ addTo: () => ({ clearLayers: vi.fn() }), clearLayers: vi.fn() }),
    polyline: () => { drawn.lines += 1; return chain(); }, circleMarker: () => chain(), marker: () => chain(), divIcon: () => ({}),
    latLngBounds: () => ({ extend: vi.fn(), isValid: () => true }),
  };
  return { default: L, ...L };
});
vi.mock("leaflet/dist/leaflet.css", () => ({}));

import { TrailsScreen } from "./Trails";

const walk = (id: string, kind: "walk" | "hike", name: string) => ({
  id, kind, name, note: "", start: "2024-03-02T08:00:00+11:00", end: null, minutes: 135, km: 9.4, kcal: 600, avg_hr: 118, max_hr: 150,
  moving_minutes: 120, ascent_m: 540, descent_m: 530, highest_m: 1922, lowest_m: 1400, pace_min_per_km: 14.4,
  start_point: [-36.9, 147.2], line: [[-36.9, 147.2], [-36.8, 147.3]], source: "apple_health_export",
});

afterEach(() => { clearResources(); drawn.lines = 0; });

describe("SirisTrails 11.22", () => {
  it("maps every walk and hike, shows the totals, and opens one with its profile", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/trails/import": () => jsonResponse({ running: false, at: "2026-11-28T00:00:00Z", added: 2, already_here: 0, no_route: 1 }),
      "/api/v1/trails/w_000000000001": (_u, init) => init.method === "PATCH" ? jsonResponse(walk("w_000000000001", "hike", "Mt Feathertop"))
        : jsonResponse({ ...walk("w_000000000001", "hike", "Mount Feathertop"), place: "Harrietville, Victoria, Australia", loop: false,
          route: [[-36.9, 147.2], [-36.8, 147.3]], profile: [[0, 1400, -36.9, 147.2], [4.7, 1700, -36.85, 147.25], [9.4, 1922, -36.8, 147.3]],
          splits: [{ km: 1, length_km: 1, minutes: 14, pace_min_per_km: 14, up_m: 60, down_m: 0 }, { km: 2, length_km: 0.4, minutes: 7, pace_min_per_km: 17.5, up_m: 20, down_m: 0 }],
          km_marks: [[1, -36.89, 147.21]] }),
      "/api/v1/trails": () => jsonResponse({ walks: [walk("w_000000000001", "hike", "Hike, Sat 2 Mar 2024"), walk("w_000000000002", "walk", "Walk, Sun 3 Mar 2024")],
        count: 2, hikes: 1, km: 18.8, hours: 4.5, ascent_m: 1080, highest_m: 1922, longest_km: 9.4, years: [2024, 2023],
        avg_km: 9.4, avg_minutes: 135, avg_pace: 14.4, countries: 2, regions: 3, places: 4,
        where: [{ country: "Australia", code: "AU", flag: "🇦🇺", walks: 2, km: 18.8, hours: 4.5,
          regions: [{ region: "Victoria", walks: 1, km: 9.4, places: 1 }, { region: "New South Wales", walks: 1, km: 9.4, places: 1 }] },
          { country: "New Zealand", code: "NZ", flag: "🇳🇿", walks: 1, km: 5, hours: 1.2, regions: [{ region: "Canterbury", walks: 1, km: 5, places: 1 }] }],
        records: { longest: { id: "w_000000000001", name: "Mount Feathertop", value: 9.4, start: "2024-03-02T08:00:00+11:00" }, longest_time: null, most_climbing: null, highest: null },
        by_year: [{ year: 2023, walks: 4, km: 20, hours: 5 }, { year: 2024, walks: 2, km: 18.8, hours: 4.5 }] }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><TrailsScreen /></MemoryRouter>);
    expect(await screen.findByText("18.8 km")).toBeInTheDocument();
    expect(screen.getByText("1,922 m")).toBeInTheDocument();
    expect(drawn.lines).toBe(2);
    expect(screen.getByText(/2 added, 0 already here, 1 with no route recorded/)).toBeInTheDocument();
    // 12.2: states per country, records, years
    expect(screen.getByText("countries")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Australia/ }));
    expect(screen.getByRole("button", { name: /New South Wales/ })).toBeInTheDocument();
    expect(screen.getByText(/Showing Australia/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Longest walk: 9.4 km/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "2023: 4 walks, 20 km" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Hike, Sat 2 Mar 2024/ }));
    expect(await screen.findByRole("heading", { name: /Mount Feathertop/ })).toBeInTheDocument();
    expect(screen.getByText(/Harrietville, Victoria, Australia/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Elevation from 1400 m to 1922 m over 9.4 km" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveTextContent("14:00 /km");               // the fastest kilometre
    expect(screen.getByText("0.40 (7:00)")).toBeInTheDocument();                    // the last part-kilometre, with its time
    await user.click(screen.getByRole("button", { name: "Rename" }));
    const name = screen.getByRole("textbox", { name: "Name" });
    await user.clear(name);
    await user.type(name, "Feathertop via the Razorback{Enter}");
    await waitFor(() => expect(calls.some((c) => c.init.method === "PATCH" && String(c.init.body).includes("Razorback"))).toBe(true));
  });
});
