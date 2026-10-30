import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FitnessWidget } from "./FitnessWidget";
import { StatusScreen } from "./Status";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const WEEK = { available: true, guest_mode: false, goal_km: 20, km: 9.2, runs: 2, exercise_minutes: 65, steps_avg: 8000,
  days: ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"].map((date, i) => ({ date, km: i === 0 ? 5.2 : i === 3 ? 4 : 0, exercise: 30, future: i > 4 })) };

describe("<FitnessWidget />", () => {
  it("shows the week against the goal and changes the goal", async () => {
    signIn();
    let goal = 20;
    const calls = mockFetch({
      "/api/v1/fitness/goal": (_u, init) => { goal = JSON.parse(String(init.body)).weekly_km; return jsonResponse({ goal_km: goal }); },
      "/api/v1/fitness": () => jsonResponse({ ...WEEK, goal_km: goal }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><FitnessWidget /></MemoryRouter>);
    expect(await screen.findByText("of 20 km this week")).toBeInTheDocument();
    expect(screen.getByText(/2 runs · 65 min exercise · 8,000 steps a day/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Goal" }));
    const box = screen.getByLabelText("Weekly running goal in km");
    await user.clear(box);
    await user.type(box, "25");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("of 25 km this week")).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/goal"))!.init.body))).toEqual({ weekly_km: 25 });
  });

  it("stays out of the way without health data", async () => {
    signIn();
    mockFetch({ "/api/v1/fitness": () => jsonResponse({ available: false, guest_mode: false, goal_km: null }) });
    const { container } = render(<MemoryRouter><FitnessWidget /></MemoryRouter>);
    await new Promise((r) => setTimeout(r, 50));
    expect(container.querySelector("[aria-label='Fitness']")).toBeNull();
  });
});

describe("System status upkeep", () => {
  it("shows backups, the update and certificates", async () => {
    signIn();
    mockFetch({
      "/api/v1/hub/upkeep": () => jsonResponse({ sirisos: { version: "3.6" }, sirisai: { backups: { newest: new Date(Date.now() - 5 * 3_600_000).toISOString(), count: 14, stale: false },
        update: { current: "2.14", latest: "2.2", available: true } }, certificates: [{ host: "siris.local", expires: "x", days_left: 9, warning: true }] }),
      "/api/v1/hub/status": () => jsonResponse({ apps: [], sample_every_minutes: 5 }),
    });
    render(<StatusScreen />);
    expect(await screen.findByText("Newest 5 h ago · 14 kept")).toBeInTheDocument();
    expect(screen.getByText("2.2 is out: update from the Inbox")).toBeInTheDocument();
    expect(screen.getByText("Runs out in 9 days")).toBeInTheDocument();
  });
});
