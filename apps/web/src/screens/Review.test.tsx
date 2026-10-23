import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ReviewScreen } from "./Review";
import type { WeeklyReview } from "../api/review";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const DATA: WeeklyReview = {
  week_of: "2026-10-19", today: "2026-10-25",
  numbers: { tasks_done: 7, notes: 12, notes_before: 8, cpd_hours: 1.5, runs: 2, run_km: 9.2, exercise_minutes: 65, meetings: 11, wrapped_up: 4 },
  done: ["Send RFI", "Book the car service"],
  quiet: [{ title: "Garden shed", days_idle: 40 }],
  next_week: { busy_days: [{ date: "2026-10-28", meetings: 3, clashes: ["Site visit and Design review"] }], meetings: 9,
    tasks: [{ id: "sirisos:x", source: "sirisos", title: "Submit the drainage report", detail: null, due: "2026-10-28", time: null, repeat: "none", group: "later" }],
    deadlines: [{ title: "Werribee Drainage", days_left: 5 }] },
  saved: null,
};

describe("<ReviewScreen />", () => {
  it("shows the week and next week, and saves what matters", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/review": (_u, init) => (init.method === "POST"
        ? jsonResponse({ focus: "Finish the report.", saved_as: "Week 43 review (2026)", at: "x" })
        : jsonResponse(DATA)),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><ReviewScreen /></MemoryRouter>);
    const week = await screen.findByRole("region", { name: "The week" });
    expect(within(week).getByText("2 · 9.2 km")).toBeInTheDocument();
    expect(within(week).getByText("Notes in Siris · 8 the week before")).toBeInTheDocument();
    expect(within(week).getByText(/Done: Send RFI · Book the car service/)).toBeInTheDocument();
    expect(screen.getByText("Untouched for 40 days")).toBeInTheDocument();
    const next = screen.getByRole("region", { name: "Next week" });
    expect(within(next).getByText("Clash: Site visit and Design review")).toBeInTheDocument();
    expect(within(next).getByText("Submit the drainage report")).toBeInTheDocument();
    expect(within(next).getByRole("link", { name: "Open next week" })).toHaveAttribute("href", "/week?start=2026-10-26");

    await user.type(screen.getByLabelText("Your note for next week"), "Finish the report.");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Saved to Siris as “Week 43 review (2026)”");
    expect(JSON.parse(String(calls.find((c) => c.init.method === "POST")!.init.body))).toEqual({ focus: "Finish the report." });
  });
});
