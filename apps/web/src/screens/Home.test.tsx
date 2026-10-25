import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Home, greeting } from "./Home";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import type { HubApp } from "../api/types";

const status = (state: HubApp["status"]["state"], detail = "") => ({ state, detail, latency_ms: 12, version: null, checked_at: "" });

const APPS: HubApp[] = [
  {
    id: "sirisai", name: "SirisAI", category: "assistant", icon: "sparkles", description: "", launch_url: "https://siris.local", launch_only: false, configured: true,
    status: status("ok"),
    widget: { title: "Today", metrics: [{ label: "Weather", value: "18° Sunny", tone: "neutral" }], items: [{ title: "Site meeting", subtitle: "Fri 09:30", url: null, tone: "neutral" }], empty: "", updated_at: "" },
  },
  {
    id: "archive", name: "Engineering Archive", category: "engineering", icon: "archive", description: "Archive", launch_url: "http://archive", launch_only: false, configured: true,
    status: status("degraded", "API key rejected: check ARCHIVE_API_KEY"),
    widget: { error: "API key rejected" },
  },
  { id: "sirisdrone", name: "SirisDrone", category: "life", icon: "plane", description: "", launch_url: null, launch_only: false, configured: false, status: status("unconfigured", "Set SIRISDRONE_URL") },
];

describe("greeting", () => {
  it("follows the time of day", () => {
    expect(greeting(new Date(2026, 0, 1, 8))).toBe("Good morning");
    expect(greeting(new Date(2026, 0, 1, 14))).toBe("Good afternoon");
    expect(greeting(new Date(2026, 0, 1, 20))).toBe("Good evening");
  });
});

describe("<Home />", () => {
  // These check the widgets themselves; what each part of the day shows is HomeDay.test.tsx.
  beforeEach(() => localStorage.setItem("sirisos.home.adaptive", "off"));
  afterEach(() => localStorage.removeItem("sirisos.home.adaptive"));

  it("shows widgets, app tiles and an app's status sheet", async () => {
    signIn("brad");
    mockFetch({
      "/api/v1/hub/apps/archive": () => jsonResponse(APPS[1]),
      "/api/v1/hub/apps": () => jsonResponse({ apps: APPS }),
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(await screen.findByText("18° Sunny")).toBeInTheDocument();
    expect(screen.getByText("Site meeting")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(", Brad");
    expect(screen.getByText(/1 app needs attention/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SirisDrone: unconfigured" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Engineering Archive: degraded" }));
    const sheet = await screen.findByRole("dialog", { name: "Engineering Archive" });
    expect(within(sheet).getByText("Needs attention")).toBeInTheDocument();
    expect(within(sheet).getByText(/ARCHIVE_API_KEY/)).toBeInTheDocument();
    expect(within(sheet).getByRole("link", { name: /open engineering archive/i })).toHaveAttribute("href", "http://archive");
  });

  it("explains a failed load", async () => {
    signIn();
    mockFetch({ "/api/v1/hub/apps": () => jsonResponse({ detail: "Database offline" }, 500) });
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Database offline");
  });

  it("adds HUD widgets from SirisAI: weather, server, calendar and activity", async () => {
    signIn("brad");
    mockFetch({
      "/api/v1/hub/apps": () => jsonResponse({ apps: APPS }),
      "/api/v1/assistant/hud": () =>
        jsonResponse({
          weather: { temperature_c: 14.7, humidity_percent: 91, wind_speed_kmh: 16.7, precipitation_mm: 0.8, conditions: "thunderstorm" },
          system: {
            cpu_percent: 3.2, cpu_count: 12,
            memory: { total_gb: 16.6, used_gb: 6.4, percent_used: 38.4 },
            disk: { "/": { total_gb: 490, used_gb: 210.6, percent_used: 45.3 } },
            temperatures_celsius: { "coretemp:Package id 0": 40 },
          },
          next_events: [{ summary: "Site meeting", start: "2026-10-03T09:30:00+10:00" }],
          autonomy: [{ time: "", local_time: "22:38", tool: "geofence_reminder_check", what: "geofence reminder check", outcome: "done" }],
          parcels: [],
        }),
    });
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(await screen.findByText("15°")).toBeInTheDocument();
    expect(screen.getByText("thunderstorm")).toBeInTheDocument();
    const server = screen.getByRole("region", { name: "Home server" });
    expect(within(server).getByText("38%")).toBeInTheDocument();
    expect(within(server).getByText(/CPU package 40°C/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Coming up" })).toHaveTextContent("Site meeting");
    expect(screen.getByRole("region", { name: "SirisAI activity" })).toHaveTextContent("Geofence reminder check");
    expect(screen.getByRole("region", { name: "Siris apps" })).toHaveTextContent("Need attention");
    expect(screen.queryByRole("region", { name: "Parcels" })).not.toBeInTheDocument();
  });

  it("holds each widget's place with a loading card until its source answers", async () => {
    signIn("brad");
    let answerHud: (r: Response) => void = () => undefined;
    mockFetch({
      "/api/v1/hub/apps": () => jsonResponse({ apps: APPS }),
      "/api/v1/assistant/hud": () => new Promise<Response>((resolve) => (answerHud = resolve)),
    });
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(await screen.findByText("18° Sunny")).toBeInTheDocument();
    const outside = screen.getByRole("region", { name: "Outside" });
    expect(outside).toHaveAttribute("aria-busy", "true");
    expect(within(outside).getByText("Loading…")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Coming up" })).toHaveAttribute("aria-busy", "true");

    answerHud(jsonResponse({ weather: { temperature_c: 14.7, humidity_percent: 91, wind_speed_kmh: 16.7, precipitation_mm: 0.8, conditions: "thunderstorm" } }));
    expect(await screen.findByText("15°")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Outside" })).not.toHaveAttribute("aria-busy");
    // A source that answers without a section drops its placeholder.
    expect(screen.queryByRole("region", { name: "Coming up" })).not.toBeInTheDocument();
  });

  it("puts the Siris App Suite near the top on phones, as one swipeable row", async () => {
    signIn("brad");
    mockFetch({ "/api/v1/hub/apps": () => jsonResponse({ apps: APPS }) });
    const original = window.matchMedia;
    window.matchMedia = ((query: string) => ({
      matches: query.includes("max-width"), media: query, addEventListener: () => {}, removeEventListener: () => {},
    })) as unknown as typeof window.matchMedia;
    try {
      render(
        <MemoryRouter>
          <Home />
        </MemoryRouter>,
      );
      const suite = await screen.findByRole("region", { name: "Siris App Suite" });
      expect(within(suite).getByRole("button", { name: "SirisDrone: unconfigured" })).toBeInTheDocument();
      expect(suite.querySelector(".app-grid--strip")).not.toBeNull();
      // Above the widgets, and only once (no second grid at the bottom).
      const now = screen.getByRole("heading", { name: "Now" });
      expect(suite.compareDocumentPosition(now) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(screen.getAllByRole("heading", { name: "Siris App Suite" })).toHaveLength(1);
    } finally {
      window.matchMedia = original;
    }
  });

  it("keeps the Siris App Suite grid at the bottom on wider screens", async () => {
    signIn("brad");
    mockFetch({ "/api/v1/hub/apps": () => jsonResponse({ apps: APPS }) });
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    const heading = await screen.findByRole("heading", { name: "Siris App Suite" });
    expect(screen.queryByRole("region", { name: "Siris App Suite" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Now" }).compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Apps" })).not.toBeInTheDocument();
  });

  it("customises Home: hides and reorders widgets, then saves the layout", async () => {
    signIn("brad");
    const calls = mockFetch({
      "/api/v1/hub/apps": () => jsonResponse({ apps: APPS }),
      "/api/v1/home/layout": (_url, init) =>
        init?.method === "PUT" ? jsonResponse(JSON.parse(String(init.body))) : jsonResponse({ phone: { order: [], hidden: [] }, desktop: { order: [], hidden: ["clock"] } }),
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(await screen.findByText("18° Sunny")).toBeInTheDocument();
    // The saved desktop layout already hides the clock.
    await waitFor(() => expect(screen.queryByRole("region", { name: "Local time" })).not.toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Customise Home" }));
    const sheet = await screen.findByRole("dialog", { name: "Customise Home" });
    expect(within(sheet).getByText(/Your desktop layout/)).toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: "Hide SirisAI" }));
    expect(screen.queryByText("18° Sunny")).not.toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: "Show Local time" }));
    expect(screen.getByRole("region", { name: "Local time" })).toBeInTheDocument();

    const puts = calls.filter((c) => c.init.method === "PUT");
    const saved = JSON.parse(String(puts[puts.length - 1].init.body));
    expect(saved.desktop.hidden).toEqual(["app:sirisai"]);
    expect(saved.phone).toEqual({ order: [], hidden: [] });

    // Now holds the clock then Siris apps; moving Siris apps up swaps them.
    await user.click(within(sheet).getByRole("button", { name: "Move Siris apps up" }));
    const now = screen.getAllByRole("region", { name: "Now" }).find((el) => !sheet.contains(el))!;
    expect(within(now).getAllByRole("region").map((r) => r.getAttribute("aria-label"))).toEqual(["Siris apps", "Local time"]);
    const last = calls.filter((c) => c.init.method === "PUT").pop()!;
    expect(JSON.parse(String(last.init.body)).desktop.order.slice(0, 2)).toEqual(["app-health", "clock"]);
  });

  it("opens with no signal on what it last fetched, saying when", async () => {
    signIn("brad");
    const at = new Date(2026, 9, 17, 7, 42).getTime();
    vi.useFakeTimers({ toFake: ["Date"], now: new Date(2026, 9, 17, 9, 0) });
    localStorage.setItem("sirisos.cache.hub:apps", JSON.stringify({ data: { apps: APPS }, updatedAt: at }));
    const online = vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    mockFetch({ "/api/v1/hub/apps": () => Promise.reject(new TypeError("Failed to fetch")) });
    try {
      render(
        <MemoryRouter>
          <Home />
        </MemoryRouter>,
      );
      // The widgets are there straight away, from the device copy.
      expect(screen.getByText("18° Sunny")).toBeInTheDocument();
      expect(screen.getByText(/Offline · showing what it had at 7:42/i)).toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    } finally {
      online.mockRestore();
      vi.useRealTimers();
    }
  });
});
