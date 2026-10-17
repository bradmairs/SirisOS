import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { StatusScreen } from "./Status";

const hours = Array.from({ length: 24 }, (_, i) => (i === 10 ? "down" : "ok"));

describe("<StatusScreen />", () => {
  it("shows each app's uptime, response time, the last 24 hours and outages", async () => {
    signIn();
    mockFetch({
      "/api/v1/hub/status": () => jsonResponse({ sample_every_minutes: 5, apps: [
        { id: "archive", name: "Engineering Archive", icon: "archive", status: { state: "down", detail: "Timed out", latency_ms: null, version: null, checked_at: "" },
          samples: 288, uptime_24h: 95.8, uptime_7d: 99.4, latency_ms_24h: 84, hours, days: [], last_problem: null,
          incidents: [{ at: 1_800_000_000, detail: "Timed out", minutes: 65 }] },
        { id: "sirisai", name: "SirisAI", icon: "sparkles", status: { state: "ok", detail: "", latency_ms: 30, version: null, checked_at: "" },
          samples: 288, uptime_24h: 100, uptime_7d: 100, latency_ms_24h: 31, hours: Array(24).fill("ok"), days: [], last_problem: null, incidents: [] },
      ] }),
    });
    render(<MemoryRouter><StatusScreen /></MemoryRouter>);
    expect(await screen.findByText("1 down")).toBeInTheDocument();
    const archive = screen.getByRole("region", { name: "Engineering Archive" });
    expect(within(archive).getByText("Down")).toBeInTheDocument();
    expect(within(archive).getByText("95.8%")).toBeInTheDocument();
    expect(within(archive).getByText("84 ms")).toBeInTheDocument();
    expect(within(archive).getByRole("img", { name: /1 hours with an outage/ })).toBeInTheDocument();
    expect(within(archive).getByText(/for 1.1 h/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "SirisAI" })).getByText(/No outages in the last 7 days/)).toBeInTheDocument();
  });
});
