import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import type { DayPlan, Patterns } from "../api/assist";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { QuickCapture } from "../components/QuickCapture";
import { AwayCard, GoalsPaceCard, PatternsCard, PlanCard } from "./Assist";
import { buildDay } from "./TodayTimeline";

afterEach(() => { clearResources(); vi.restoreAllMocks(); vi.useRealTimers(); localStorage.clear(); });

const body = (c: { init: RequestInit }) => JSON.parse(String(c.init.body));
const wrap = (node: React.ReactNode) => render(<MemoryRouter>{node}</MemoryRouter>);

describe("SirisOS 11.3", () => {
  it("files a spend from quick capture onto the budget, with undo", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/capture/route": () => jsonResponse({ handled: true, kind: "spend", where: "Budget · Groceries", said: "$42.00 at Woolworths", url: "/budget", undo: { kind: "spend", id: "m1" } }),
      "/api/v1/capture/undo": () => jsonResponse({ undone: true }),
      "/api/v1/brain/capture": () => jsonResponse({ title: "x" }),
    });
    render(<QuickCapture onClose={() => undefined} />);
    await userEvent.type(screen.getByLabelText("Capture text"), "spent $42 at Woolworths");
    await userEvent.click(screen.getByRole("button", { name: /Save/ }));
    expect(await screen.findByText("Added to Budget · Groceries: $42.00 at Woolworths.")).toBeInTheDocument();
    expect(calls.some((c) => c.url.includes("/brain/capture"))).toBe(false);  // not sent to Siris as well
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByText(/Taken back/)).toBeInTheDocument();
    expect(body(calls.find((c) => c.url.endsWith("/capture/undo"))!)).toEqual({ undo: { kind: "spend", id: "m1" } });
  });

  it("sends anything else to Siris as before", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/capture/route": () => jsonResponse({ handled: false }),
      "/api/v1/assistant/brain/capture": () => jsonResponse({ title: "Solar on the shed" }),
      "/api/v1/brain/capture": () => jsonResponse({ title: "Solar on the shed" }),
    });
    render(<QuickCapture onClose={() => undefined} />);
    await userEvent.type(screen.getByLabelText("Capture text"), "An idea about solar on the shed");
    await userEvent.click(screen.getByRole("button", { name: /Save/ }));
    expect(await screen.findByText(/Saved to Siris' inbox/)).toBeInTheDocument();
    expect(calls.filter((c) => c.url.includes("capture/route"))).toHaveLength(1);
  });

  it("shows the plan for the rest of today and what won't fit", async () => {
    signIn();
    const p: DayPlan = { date: "2026-11-24", readiness: 35, until: "20:00", free_minutes: 60, tasks: 3, events: [],
      blocks: [{ start: "23:30", end: "23:45", minutes: 15, kind: "quick", title: "Call Sam", task_id: "t1", area: "personal" },
        { start: "23:45", end: "23:59", minutes: 14, kind: "goal", title: "Run about 8 km", task_id: null, area: "personal", goal: "Run 1,200 km" }],
      left: [{ id: "t3", title: "Draft design notes", why: "Low readiness today: one deep block is enough." }] };
    mockFetch({ "/api/v1/plan/today": () => jsonResponse(p) });
    wrap(<PlanCard />);
    expect(await screen.findByText("Call Sam")).toBeInTheDocument();
    expect(screen.getByText(/for Run 1,200 km/)).toBeInTheDocument();
    expect(screen.getByText(/1 won't fit today: Draft design notes/)).toBeInTheDocument();
    expect(screen.getByText("Readiness is low, so it's a lighter plan.")).toBeInTheDocument();
  });

  it("says what happened while you were away, and Got it marks it seen", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/away/done": () => jsonResponse({ ok: true }),
      "/api/v1/away": () => jsonResponse({ away: true, away_for: "2 days", keys: ["inbox:a1"],
        items: [{ kind: "inbox", title: "1 thing needs you", lines: ["Backup failed"], url: "/inbox" }, { kind: "tasks", title: "Tasks: 2 overdue", lines: [], url: "/tasks" }] }),
    });
    wrap(<AwayCard />);
    expect(await screen.findByText("1 thing needs you")).toBeInTheDocument();
    expect(screen.getByText("2 days")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Got it" }));
    await waitFor(() => expect(screen.queryByText("1 thing needs you")).not.toBeInTheDocument());
    expect(body(calls.find((c) => c.url.endsWith("/away/done"))!)).toEqual({ keys: ["inbox:a1"] });
  });

  it("starts the clock again when you're not away", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/away/touch": () => jsonResponse({ ok: true }), "/api/v1/away": () => jsonResponse({ away: false }) });
    const { container } = wrap(<AwayCard />);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/away/touch"))).toBe(true));
    expect(container).toBeEmptyDOMElement();
  });

  it("shows patterns and goals off pace", async () => {
    signIn();
    const pt: Patterns = { at: "x", days: 120, sources: [], patterns: [{ id: "drinks-hrv", text: "After drinking, your HRV next morning 57 ms on average, against 72 ms after a day without.", try: "Try a dry week and watch whether HRV comes back up.", strength: 1.2, worse: true, days: 99 }] };
    mockFetch({
      "/api/v1/patterns": () => jsonResponse(pt),
      "/api/v1/goals/steer": () => jsonResponse({ year: 2026, through_year: 90, goals: [], behind: [{ id: "g1", title: "Run 1,200 km", state: "behind", value: 900, target: 1200, unit: "km", projected: 1007.7, projected_percent: 84, weekly: 50, weeks_left: 6, step: { text: "Run 50 km this week: 4 runs of about 12 km." } }] }),
    });
    wrap(<><PatternsCard /><GoalsPaceCard /></>);
    expect(await screen.findByText(/After drinking, your HRV/)).toBeInTheDocument();
    expect(await screen.findByText(/On pace for 1,008 of 1,200 km\. Run 50 km this week/)).toBeInTheDocument();
  });

  it("puts repeating charges due soon on the timeline, once", () => {
    const now = new Date(2026, 10, 24, 9, 0);
    const day = buildDay(now, {
      bills: [{ id: 1, label: "Netflix (SirisAI)", due_date: "2026-11-26" }],
      charges: [{ id: "c1", name: "Spotify", amount: 13.99, next: "2026-11-25", status: null },
        { id: "c2", name: "Netflix", amount: 22.99, next: "2026-11-26", status: null },
        { id: "c3", name: "Gym", amount: 20, next: "2026-12-10", status: null },
        { id: "c4", name: "Stan", amount: 12, next: "2026-11-25", status: "cancelling" }],
    });
    expect(day.soon.map((e) => e.text)).toEqual(["Spotify $13.99", "Netflix (SirisAI)"]);
  });
});
