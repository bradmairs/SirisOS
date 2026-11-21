import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import type { Bins, Containers, Fuel, Garden, Internet, Tonight, Weekend } from "../api/routines";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { BinsCard, ContainerUpdatesCard, FuelCard, GardenCard, InternetCard, WatchTonightCard, WeekendCard, WeekScreen } from "./Routines";

afterEach(() => { clearResources(); vi.restoreAllMocks(); vi.useRealTimers(); localStorage.clear(); });

const at = (iso: string) => { vi.useFakeTimers({ toFake: ["Date"] }); vi.setSystemTime(new Date(iso)); };
const wrap = (node: React.ReactNode) => render(<MemoryRouter>{node}</MemoryRouter>);

const station = (id: string, name: string, price: number, km: number) => ({ id, name, brand: null, address: "", lat: -37.5, lon: 144.9, price, updated: null, off_km: 0.4, km_in: km, maps: `https://maps.apple.com/?daddr=${id}` });
const fuel = (over: Partial<Fuel> = {}): Fuel => ({
  settings: { on: true, weekday: 2, leave: "06:00", fuel_type: "U91", first_km: 30, off_route_km: 1.5, destination: { name: "Shepparton", lat: -36.38, lon: 145.4 }, home: null },
  configured: true, attribution: "© State of Victoria accessed via the Victorian Government Service Victoria Platform",
  best: station("s2", "BP Wallan", 176.5, 25.6), options: [station("s2", "BP Wallan", 176.5, 25.6), station("s1", "United Craigieburn", 181.9, 11.1)],
  average: 179.2, saving_cents: 2.7, route_km: 30, note: "Prices are about a day old (Fair Fuel's open data).", for: "2026-12-02", ...over,
});

describe("SirisOS 10.4", () => {
  it("shows the cheapest fuel on the Shepparton drive, only when it's due", async () => {
    signIn();
    mockFetch({ "/api/v1/fuel": () => jsonResponse(fuel()) });
    wrap(<FuelCard />);
    expect(await screen.findByText("BP Wallan · 176.5¢")).toBeInTheDocument();
    expect(screen.getByText(/2.7¢ under the average/)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Map" })).toHaveLength(2);
    expect(screen.getByText(/State of Victoria/)).toBeInTheDocument();
  });

  it("keeps the fuel card away on other days", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/fuel": () => jsonResponse(fuel({ for: null })) });
    const { container } = wrap(<FuelCard />);
    await waitFor(() => expect(calls.length).toBe(1));
    expect(container).toBeEmptyDOMElement();
  });

  it("picks the weekend's windows Thursday to Sunday and none midweek", async () => {
    signIn();
    const w: Weekend = { days: ["2026-11-28", "2026-11-29"], recover: false, note: null, readiness: null,
      routes: [{ id: "r1", name: "You Yangs loop", kind: "hike", hours: 2.5, km: 9, link: "https://example.org/yy", notes: "" }],
      windows: [{ date: "2026-11-28", start: "06:00", end: "10:00", hours: 4, low_c: 14, high_c: 19, rain_chance: 5, conditions: "mainly clear", score: 1,
        route: { id: "r1", name: "You Yangs loop", kind: "hike", hours: 2.5, km: 9, link: "https://example.org/yy", notes: "" } }] };
    const calls = mockFetch({ "/api/v1/weekend": () => jsonResponse(w) });
    at("2026-11-26T17:30:00");
    const { unmount } = wrap(<WeekendCard />);
    expect(await screen.findByText("Sat 6am–10am")).toBeInTheDocument();
    expect(screen.getByText(/You Yangs loop \(2.5 h\)/)).toBeInTheDocument();
    unmount(); clearResources(); calls.length = 0;
    at("2026-11-24T17:30:00");
    const { container } = wrap(<WeekendCard />);
    expect(container).toBeEmptyDOMElement();
    expect(calls).toHaveLength(0);
  });

  it("puts the bins out the night before", async () => {
    signIn();
    const b: Bins = { bins: [], next: { date: "2026-11-27", kinds: ["rubbish", "green"], text: "Rubbish and green waste" }, show: true, when: "tonight" };
    mockFetch({ "/api/v1/bins": () => jsonResponse(b) });
    wrap(<BinsCard />);
    expect(await screen.findByText("Rubbish and green waste")).toBeInTheDocument();
    expect(screen.getByText("Bins out tonight")).toBeInTheDocument();
  });

  it("says water the garden and runs the protocol", async () => {
    signIn();
    const g: Garden = { on: true, protocol: "Water the garden", last_watered: null, water: true, why: "Dry for days." };
    const calls = mockFetch({
      "/api/v1/garden/watered": () => jsonResponse({ ...g, last_watered: new Date().toLocaleDateString("en-CA") }),
      "/api/v1/garden": () => jsonResponse(g),
      "/api/v1/assistant/protocols": () => jsonResponse({ ok: true }),
    });
    wrap(<GardenCard />);
    await userEvent.click(await screen.findByRole("button", { name: "Water now" }));
    await waitFor(() => expect(screen.queryByText("Dry for days.")).not.toBeInTheDocument());
    expect(calls.some((c) => c.url.includes("/assistant/protocols/Water%20the%20garden/run"))).toBe(true);
  });

  it("suggests what to watch from 6pm with what's new this week", async () => {
    signIn();
    const t: Tonight = { available: true, minutes_to_bed: 150, bedtime: "22:30", plex: true, on_deck: [], new_unwatched: [],
      picks: [{ title: "Slow Horses: S04E03", type: "episode", why: "Carry on where you left off" }],
      episodes: [{ series: "Severance", season: 2, number: 4, air_date: "2026-11-28" }], movies: [{ title: "Dune", kind: "digital" }] };
    mockFetch({ "/api/v1/watch/tonight": () => jsonResponse(t) });
    at("2026-11-26T20:00:00");
    wrap(<WatchTonightCard />);
    expect(await screen.findByText("Slow Horses: S04E03")).toBeInTheDocument();
    expect(screen.getByText("2 h 30 min till bed")).toBeInTheDocument();
    expect(screen.getByText(/Severance S02E04/)).toBeInTheDocument();
    expect(screen.getByText("Dune (digital)")).toBeInTheDocument();
  });

  it("updates containers and charts the internet against the plan", async () => {
    signIn();
    const c: Containers = { available: true, updates: [{ container: "sonarr", image: "linuxserver/sonarr", current: "4.0.1", available: "4.0.2" }, { container: "radarr" }], up_to_date: [], skipped: {}, running: false };
    const i: Internet = { available: true, speeds: [], outages: [{ start: "2026-11-25T03:00:00Z", end: "2026-11-25T03:10:00Z", seconds: 600 }],
      daily: [{ date: "2026-11-24", down: 90, up: 18, tests: 4 }, { date: "2026-11-25", down: 40, up: 18, tests: 4 }], plan: { down: 100, up: 20 }, slow: ["2026-11-25"], share_of_plan: 40 };
    const calls = mockFetch({
      "/api/v1/lab/containers/update": () => jsonResponse({ started: 1, order: ["sonarr"], message: "Updating sonarr" }),
      "/api/v1/lab/containers": () => jsonResponse(c),
      "/api/v1/lab/internet": () => jsonResponse(i),
    });
    wrap(<><ContainerUpdatesCard /><InternetCard /></>);
    expect(await screen.findByText("4.0.1 → 4.0.2", { exact: false })).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Update" })[0]);
    expect(await screen.findByText("Updating sonarr")).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((x) => x.url.endsWith("/containers/update"))!.init.body))).toEqual({ containers: ["sonarr"] });
    expect(screen.getByRole("img", { name: /against a 100 Mbps plan/ })).toBeInTheDocument();
    expect(screen.getByText("40% of plan lately")).toBeInTheDocument();
    expect(screen.getByText(/1 dropout, the last/)).toBeInTheDocument();
  });

  it("sets up bins and routes on Around the week", async () => {
    signIn();
    const saved: unknown[] = [];
    mockFetch({
      "/api/v1/weekend/routes": (_u, init) => { saved.push(JSON.parse(String(init.body))); return jsonResponse({ days: [], windows: [], routes: [{ id: "a", name: "Merri Creek", kind: "walk", hours: 1, km: null, link: null, notes: "" }], readiness: null, recover: false, note: null }); },
      "/api/v1/weekend": () => jsonResponse({ days: [], windows: [], routes: [], readiness: null, recover: false, note: null }),
      "/api/v1/bins": (_u, init) => { if (init.method === "PUT") saved.push(JSON.parse(String(init.body))); return jsonResponse({ bins: init.method === "PUT" ? JSON.parse(String(init.body)).bins : [], next: null, show: false, when: null }); },
      "/api/v1/fuel": () => jsonResponse(fuel({ configured: false, why: "Add SIRISOS_FAIR_FUEL_KEY", for: null })),
      "/api/v1/bedroom": () => jsonResponse({ temp_entity: null, humidity_entity: null, low: 17, high: 20, show: false }),
      "/api/v1/garden": () => jsonResponse({ on: false, protocol: null, last_watered: null }),
    });
    wrap(<WeekScreen />);
    await userEvent.type(await screen.findByLabelText("Route name"), "Merri Creek");
    await userEvent.click(screen.getAllByRole("button", { name: "Add" })[0]);
    expect(await screen.findByText("Merri Creek")).toBeInTheDocument();
    expect(saved[0]).toEqual({ routes: [{ name: "Merri Creek", kind: "walk", hours: 1, link: null }] });
    expect(screen.getByText("Add SIRISOS_FAIR_FUEL_KEY")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("How often"), "2");
    await userEvent.type(screen.getByLabelText("A collection day"), "2026-11-06");
    await userEvent.click(screen.getAllByRole("button", { name: "Add" })[1]);
    expect(await screen.findByText("Every 2 weeks · Fridays", { exact: false })).toBeInTheDocument();
    expect(saved[1]).toEqual({ bins: [{ kind: "rubbish", every_weeks: 2, first: "2026-11-06" }] });
  });
});
