import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

// jsdom can't draw a map: Leaflet is replaced by something that records what's drawn.
const drawn: { lines: number } = { lines: 0 };
vi.mock("leaflet", () => {
  const chain = () => ({ addTo: () => chain(), bindTooltip: () => chain(), on: () => chain(), getBounds: () => ({ isValid: () => true }) });
  const L = {
    map: () => ({ fitBounds: vi.fn(), setView: vi.fn(), invalidateSize: vi.fn(), remove: vi.fn() }),
    tileLayer: () => chain(), control: { layers: () => chain() }, layerGroup: () => ({ addTo: () => ({ clearLayers: vi.fn() }), clearLayers: vi.fn() }),
    polyline: () => { drawn.lines += 1; return chain(); }, circleMarker: () => chain(),
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
        : jsonResponse({ ...walk("w_000000000001", "hike", "Hike, Sat 2 Mar 2024"), route: [[-36.9, 147.2], [-36.8, 147.3]], profile: [[0, 1400], [9.4, 1922]] }),
      "/api/v1/trails": () => jsonResponse({ walks: [walk("w_000000000001", "hike", "Hike, Sat 2 Mar 2024"), walk("w_000000000002", "walk", "Walk, Sun 3 Mar 2024")],
        count: 2, hikes: 1, km: 18.8, hours: 4.5, ascent_m: 1080, highest_m: 1922, longest_km: 9.4, years: [2024] }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><TrailsScreen /></MemoryRouter>);
    expect(await screen.findByText("18.8 km")).toBeInTheDocument();
    expect(screen.getByText("1,922 m")).toBeInTheDocument();
    expect(drawn.lines).toBe(2);
    expect(screen.getByText(/2 added, 0 already here, 1 with no route recorded/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Hike, Sat 2 Mar 2024/ }));
    expect(await screen.findByRole("img", { name: "Elevation from 1400 m to 1922 m" })).toBeInTheDocument();
    const name = screen.getByRole("textbox", { name: "Name" });
    await user.clear(name);
    await user.type(name, "Mt Feathertop");
    await user.click(screen.getByRole("button", { name: "Done" }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "PATCH" && String(c.init.body).includes("Mt Feathertop"))).toBe(true));
  });
});
