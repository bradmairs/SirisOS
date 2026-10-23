import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import { TrendsScreen } from "./Trends";

const months = Array.from({ length: 12 }, (_, i) => {
  const m = ((10 + i) % 12) + 1;
  const y = m >= 11 ? 2025 : 2026;
  return { month: `${y}-${String(m).padStart(2, "0")}`, cpd_hours: i === 11 ? 2.5 : 3, running_km: i * 2, exercise_minutes: 0, steps: null,
    tasks_done: i, inbox: i < 10 ? null : 4, journal_days: i === 11 ? 5 : 0, wrapups: 0, reviews: 0 };
});
const data = { today: "2026-10-23", months, cpd: { window_total: 96.5, required: 150 }, journal: { current: 3, longest: 9 },
  since: { health: "2025-11-01", log: "2026-10-01" }, available: { health: true } };

describe("<TrendsScreen />", () => {
  it("shows each measure for 12 months, with a readout per month and a table", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/trends": () => jsonResponse(data) });
    const user = userEvent.setup();
    render(<MemoryRouter><TrendsScreen /></MemoryRouter>);
    const cpd = await screen.findByRole("region", { name: "CPD hours" });
    expect(within(cpd).getByText("35.5 h")).toBeInTheDocument();
    expect(within(cpd).getByText("96.5 of 150 in your three-year window")).toBeInTheDocument();
    expect(within(cpd).getByText(/October 2026 so far:/)).toBeInTheDocument();
    const running = screen.getByRole("region", { name: "Running" });
    expect(within(running).getByText("132 km")).toBeInTheDocument();
    fireEvent.mouseEnter(within(running).getByRole("listitem", { name: "December 2025: 2 km" }));
    expect(within(running).getByText(/December 2025:/).parentElement).toHaveTextContent("December 2025: 2 km");
    expect(within(screen.getByRole("region", { name: "Inbox at its busiest" })).getByText(/^October 2026 so far:/).parentElement).toHaveTextContent("so far: 4");
    expect(screen.getByText("3-day streak now · longest 9")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Table/ }));
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(13);
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("October 2026");
  });
});
