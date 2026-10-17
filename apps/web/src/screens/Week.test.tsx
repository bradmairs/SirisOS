import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { WeekScreen } from "./Week";
import type { Week } from "../api/week";

const day = (date: string, extra: Partial<Week["days"][number]> = {}) => ({ date, events: [], forecast: null, due: [], cpd_hours: 0, ...extra });

function week(start: string): Week {
  return {
    start, end: "2026-10-19", today: "2026-10-15",
    days: [
      day("2026-10-12"), day("2026-10-13", { cpd_hours: 3 }),
      day("2026-10-14", { events: [{ title: "Stormwater webinar (IPWEA)", start: "2026-10-14T12:00:00+11:00", end: "2026-10-14T13:30:00+11:00", all_day: false, location: "Online", calendar: "Work", cpd: { hours: 1.5, category: "area" } }] }),
      day("2026-10-15", { forecast: { conditions: "Showers", high_c: 18, low_c: 9, rain_chance_percent: 80 } }),
      day("2026-10-16", { due: [{ title: "Referee 2 for CPEng", kind: "goal", source: "Career" }] }),
      day("2026-10-17"), day("2026-10-18"),
    ],
    overdue: [{ title: "Send levels to Dana", detail: "Werribee Drainage · 3 days late", source: "Second Brain" }],
    cpd: { logged: 3, planned: 1.5 }, guest_mode: false, unavailable: [],
  };
}

describe("<WeekScreen />", () => {
  it("shows each day with events, forecast, what's due and the week's CPD, and moves between weeks", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/week": (url) => jsonResponse(week(url.includes("start=2026-10-19") ? "2026-10-19" : "2026-10-12")) });
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/week"]}>
        <WeekScreen />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "This week" })).toBeInTheDocument();
    const today = screen.getByRole("region", { name: /Thursday/ });
    expect(today).toHaveTextContent("Today");
    expect(today).toHaveTextContent("18°");
    expect(today).toHaveTextContent("80%");
    expect(screen.getByText("Stormwater webinar (IPWEA)").closest("li")).toHaveTextContent("CPD 1.5 h");
    expect(screen.getByText("Referee 2 for CPEng").closest("li")).toHaveTextContent("Due · Career");
    expect(within(screen.getByRole("region", { name: "Overdue" })).getByText("Send levels to Dana")).toBeInTheDocument();
    expect(screen.getByText(/CPD this week: 3 h in your Engineers Australia import, 1.5 h on the calendar/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Next week" }));
    expect(await screen.findByRole("button", { name: "Today" })).toBeInTheDocument();
    expect(calls.some((c) => c.url === "/api/v1/week?start=2026-10-19")).toBe(true);
  });
});
