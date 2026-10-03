import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
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
    id: "apd-pm", name: "Project Management", category: "work", icon: "kanban", description: "APD", launch_url: "http://apd", launch_only: false, configured: true,
    status: status("degraded", "Login rejected: check APD_PM_EMAIL/APD_PM_PASSWORD"),
    widget: { error: "Login rejected" },
  },
  { id: "helmarr", name: "Helmarr", category: "life", icon: "film", description: "", launch_url: null, launch_only: true, configured: false, status: status("unconfigured", "Set HELMARR_URL") },
];

describe("greeting", () => {
  it("follows the time of day", () => {
    expect(greeting(new Date(2026, 0, 1, 8))).toBe("Good morning");
    expect(greeting(new Date(2026, 0, 1, 14))).toBe("Good afternoon");
    expect(greeting(new Date(2026, 0, 1, 20))).toBe("Good evening");
  });
});

describe("<Home />", () => {
  it("shows widgets, app tiles and an app's status sheet", async () => {
    signIn("brad");
    mockFetch({
      "/api/v1/hub/apps/apd-pm": () => jsonResponse(APPS[1]),
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
    expect(screen.getByRole("button", { name: "Helmarr: unconfigured" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Project Management: degraded" }));
    const sheet = await screen.findByRole("dialog", { name: "Project Management" });
    expect(within(sheet).getByText("Needs attention")).toBeInTheDocument();
    expect(within(sheet).getByText(/APD_PM_PASSWORD/)).toBeInTheDocument();
    expect(within(sheet).getByRole("link", { name: /open project management/i })).toHaveAttribute("href", "http://apd");
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
    expect(screen.getByRole("region", { name: "Siris activity" })).toHaveTextContent("Geofence reminder check");
    expect(screen.getByRole("region", { name: "Siris apps" })).toHaveTextContent("Need attention");
    expect(screen.queryByRole("region", { name: "Parcels" })).not.toBeInTheDocument();
  });
});
