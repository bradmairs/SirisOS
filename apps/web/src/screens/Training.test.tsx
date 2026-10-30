import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { clearResources } from "../api/resource";
import type { Training } from "../api/training";
import { TodaysRunWidget, TrainingScreen } from "./Training";

const none: Training = { today: "2026-10-30", health: true, recovery: { level: "good", notes: [], known: true }, plan: null, this_week: null, session: null, recent_weekly_km: 18.5 };
const planned: Training = {
  ...none,
  recovery: { level: "easy", notes: ["You slept 5.9 h, 1.6 h under your usual"], known: true },
  plan: { race: { name: "Run Melbourne", date: "2027-01-24", distance_km: 10 }, start_km: 18.5, days_to_go: 86, weeks: [
    { week_of: "2026-10-26", km: 18.5, kind: "build", done_km: 9, sessions: [{ date: "2026-10-31", kind: "long", km: 7, title: "Long run, 7 km, easy pace" }] }] },
  this_week: { week_of: "2026-10-26", km: 18.5, kind: "build", done_km: 9, sessions: [] },
  session: { date: "2026-10-30", kind: "quality", km: 6, title: "Easy run, 4 km instead (recovery's down)", changed: true },
};
const status = { has_key: false, key_hint: null, made: null, path: "/api/v1/health/import", last: null, last_ok: null };

describe("training", () => {
  it("adds a race, shows today adjusted for recovery, and makes a health key", async () => {
    signIn();
    clearResources();
    const calls = mockFetch({
      "/api/v1/training/race": () => jsonResponse(planned),
      "/api/v1/training/feed": () => jsonResponse({ path: "/api/v1/training/calendar.ics?t=abc123abc123" }),
      "/api/v1/training": () => jsonResponse(none),
      "/api/v1/health/import/key": () => jsonResponse({ key: "hk_secret123", path: "/api/v1/health/import" }),
      "/api/v1/health/import/status": () => jsonResponse(status),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><TrainingScreen /></MemoryRouter>);
    expect(await screen.findByText(/18.5 km a week lately/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add a race" }));
    const form = screen.getByRole("region", { name: "Race" });
    await user.type(within(form).getByLabelText("Race"), "Run Melbourne");
    await user.type(within(form).getByLabelText("Race day"), "2027-01-24");
    await user.click(within(form).getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Easy run, 4 km instead (recovery's down)")).toBeInTheDocument();
    expect(screen.getByText(/Recovery's down: take it easier: You slept 5.9 h/)).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/training/race"))!.init.body))).toMatchObject({ name: "Run Melbourne", date: "2027-01-24", distance_km: 10, start_km: null });
    expect(await screen.findByRole("link", { name: "Subscribe" })).toHaveAttribute("href", expect.stringMatching(/^webcal:\/\/.*calendar\.ics\?t=abc123abc123$/));

    await user.click(screen.getByRole("button", { name: "Make a key" }));
    expect(await screen.findByText("hk_secret123")).toBeInTheDocument();
  });

  it("Home's card shows today's run only with a race", async () => {
    signIn();
    clearResources();
    mockFetch({ "/api/v1/training": () => jsonResponse(planned) });
    render(<MemoryRouter><TodaysRunWidget /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Today's run" });
    expect(within(card).getByText("86 days to Run Melbourne")).toBeInTheDocument();
    expect(within(card).getByText("This week: 9 of 18.5 km")).toBeInTheDocument();
    clearResources();
    mockFetch({ "/api/v1/training": () => jsonResponse(none) });
    const { container } = render(<MemoryRouter><TodaysRunWidget /></MemoryRouter>);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
