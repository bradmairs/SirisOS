import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import type { WeeklyReview } from "../api/review";
import type { Habit } from "../api/mind";
import type { Renewal } from "../api/renewals";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { HabitsHomeWidget } from "./HabitsWidget";
import { RenewalsCard } from "./RenewalsCard";
import { ReviewScreen } from "./Review";
import { PhoneWidgetCard } from "./PhoneWidgetCard";
import { buildDay } from "./TodayTimeline";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

const habit = (over: Partial<Habit>): Habit => ({ id: "h1", name: "Stretch", created: "2026-11-01", streak: 0, best: 0, today: false, rate: 0, month: [], ...over });

describe("SirisOS 9.4", () => {
  it("ticks today's habits from Home, and warns of a streak at risk in the evening", async () => {
    signIn();
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date(2026, 10, 13, 19, 0) });
    const calls = mockFetch({
      "/api/v1/mind/habits/h1/check": () => jsonResponse({ habits: [habit({ today: true, streak: 6 })] }),
      "/api/v1/mind/habits": () => jsonResponse({ habits: [habit({ streak: 5 }), habit({ id: "h2", name: "Read", today: true, streak: 2 })] }),
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<MemoryRouter><HabitsHomeWidget /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Habits" });
    expect(within(card).getByText("Keep your 5-day streak")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "1/2 today" })).toHaveAttribute("href", "/health?view=habits");
    await user.click(within(card).getByRole("button", { name: "Stretch: done today" }));
    expect(await within(card).findByText("6-day streak")).toBeInTheDocument();
    expect(calls.some((c) => c.url === "/api/v1/mind/habits/h1/check")).toBe(true);
    vi.useRealTimers();
  });

  it("keeps documents and renewals, soonest first, and takes a new date when renewed", async () => {
    signIn();
    let list: Renewal[] = [{ id: "r1", name: "Car rego", kind: "rego", expires: "2026-12-01", note: "", days_left: 18, state: "soon" }];
    const calls = mockFetch({
      "/api/v1/renewals/r1": (_u, init) => { list = [{ ...list[0], expires: JSON.parse(String(init.body)).expires, days_left: 383, state: "fine" }]; return jsonResponse({ renewals: list }); },
      "/api/v1/renewals": (_u, init) => {
        if (init.method === "POST") list = [...list, { id: "r2", ...JSON.parse(String(init.body)), note: "", days_left: 900, state: "fine" }];
        return jsonResponse({ renewals: list });
      },
    });
    const user = userEvent.setup();
    render(<MemoryRouter><RenewalsCard /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Documents and renewals" });
    expect(within(card).getByText("Car rego · in 18 days")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Add one" }));
    await user.type(within(card).getByLabelText("Expires"), "2029-05-01");
    await user.click(within(card).getByRole("button", { name: "Add" }));
    expect(await within(card).findByText("Passport")).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.init.method === "POST")!.init.body))).toEqual({ name: "Passport", kind: "passport", expires: "2029-05-01" });
  });

  it("puts a renewal due this week on the Today timeline", () => {
    const day = buildDay(new Date(2026, 10, 13, 9), { renewals: [{ id: "r1", name: "Car rego", days_left: 3 }, { id: "r2", name: "Passport", days_left: 300 }] });
    expect(day.soon.map((e) => e.text)).toEqual(["Car rego expires in 3 days"]);
  });

  it("shows mood, mindful minutes and habits in the weekly review", async () => {
    signIn();
    const data: WeeklyReview = {
      week_of: "2026-11-09", today: "2026-11-13",
      numbers: { tasks_done: 1, notes: 0, notes_before: 0, cpd_hours: 0, runs: null, run_km: null, exercise_minutes: null, meetings: null, wrapped_up: 0 },
      done: [], quiet: [], next_week: { busy_days: [], meetings: null, tasks: [], deadlines: [] }, saved: null,
      mind: { mood: 0.4, word: "Slightly pleasant", mood_before: 0.1, mindful_minutes: 45, mindful_before: 20, habits: [{ name: "Stretch", done: 4, of: 5 }] },
    };
    mockFetch({ "/api/v1/review": () => jsonResponse(data) });
    render(<MemoryRouter><ReviewScreen /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Mind and habits this week" });
    expect(card).toHaveTextContent("Mood: slightly pleasant, up on last week. 45 mindful minutes (20 last week).");
    expect(within(card).getByText("4 of 5 days")).toBeInTheDocument();
  });

  it("sets up the iPhone widget with its own key and a script to copy", async () => {
    signIn();
    mockFetch({ "/api/v1/glance/key": (_u, init) => (init.method === "POST" ? jsonResponse({ key: "glance_abc" }) : jsonResponse({ set: false, created: null })) });
    const user = userEvent.setup();
    const writeText = vi.fn(async () => {});  // after setup, which puts in its own clipboard
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<MemoryRouter><PhoneWidgetCard /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Set up the widget" }));
    await user.click(await screen.findByRole("button", { name: "Copy the script" }));
    expect(writeText).toHaveBeenCalledTimes(1);
    const script = String((writeText.mock.calls[0] as unknown[])[0]);
    expect(script).toContain(`${window.location.origin}/api/v1/glance?key=glance_abc`);
    expect(script).toContain("applyTimerStyle");
    expect(screen.getByRole("status")).toHaveTextContent("The script copied.");
  });
});
