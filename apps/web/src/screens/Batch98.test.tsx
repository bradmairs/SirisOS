import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { Dock } from "../components/Dock";
import { useShowMore } from "../components/ShowMore";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { BodyRingsWidget } from "./Health";
import { DayPicker } from "./HealthMind";
import { HabitsHomeWidget } from "./HabitsWidget";
import { TimesheetCard } from "./Work";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

describe("SirisOS 9.8", () => {
  it("tapping the tab you're on goes back to the top", async () => {
    signIn();
    mockFetch({ "/api/v1/attention": () => jsonResponse({ items: [], counts: { open: 0, urgent: 0 } }), "/api/v1": () => jsonResponse({}) });
    const to = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    render(<MemoryRouter initialEntries={["/"]}><Dock /></MemoryRouter>);
    await userEvent.click(screen.getByRole("link", { name: /Home/ }));
    expect(to).toHaveBeenCalledWith(expect.objectContaining({ top: 0 }));
  });

  it("says how many more are hidden, not the total", async () => {
    function List() {
      const { shown, toggle } = useShowMore(["a", "b", "c", "d"]);
      return <div>{shown.join(",")}{toggle}</div>;
    }
    render(<List />);
    expect(screen.getByRole("button", { name: "Show 1 more" })).toBeInTheDocument();
  });

  it("shows readiness, strain and battery as three small rings", async () => {
    signIn();
    mockFetch({ "/api/v1/health/today": () => jsonResponse({
      readiness: { score: 72, band: "Steady", advice: "", contributors: [], summary: "" },
      strain: { today: 8.4, target: [10, 14], status: "under", advice: "", max_hr: 190, workouts: [], week: [] },
      energy: { now: 61, start: 80, wake: "06:30", timeline: [], spent: { awake: 0, activity: 0, stress: 0 }, regained: 0, summary: "", estimated: false } }) });
    render(<MemoryRouter><BodyRingsWidget /></MemoryRouter>);
    expect(await screen.findByRole("link", { name: "Readiness: 72, Steady" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Strain: 8.4, aim 10–14" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Battery: 61, now" })).toBeInTheDocument();
  });

  it("picks a habit's days, and Home shows only today's", async () => {
    const changed: number[][] = [];
    render(<DayPicker label="Days" days={[0, 2]} onChange={(d) => changed.push(d)} />);
    await userEvent.click(screen.getByRole("button", { name: "Friday" }));
    expect(changed[0]).toEqual([0, 2, 4]);
    signIn();
    mockFetch({ "/api/v1/mind/habits": () => jsonResponse({ habits: [
      { id: "a", name: "Gym", created: "2026-11-01", streak: 2, best: 2, today: false, rate: 100, days: [0, 2, 4], due_today: false, when: "Mon, Wed, Fri", month: [] },
      { id: "b", name: "Read", created: "2026-11-01", streak: 5, best: 5, today: false, rate: 80, days: [], due_today: true, when: "Every day", month: [] }] }) });
    render(<MemoryRouter><HabitsHomeWidget /></MemoryRouter>);
    expect(await screen.findByText("Read")).toBeInTheDocument();
    expect(screen.queryByText("Gym")).toBeNull();
  });

  it("notes timesheet items for a day and copies the week", async () => {
    signIn();
    const week = { week_of: "2026-11-16", today: "2026-11-18", hours: 1.5, text: "Wed 18 Nov (1.5 h)", recent_codes: [], by_code: [{ code: "No code", hours: 1.5 }],
      days: ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22"].map((date) => ({ date, hours: date === "2026-11-18" ? 1.5 : 0,
        entries: date === "2026-11-18" ? [{ id: "x", date, what: "Pump station review", hours: 1.5, code: "" }] : [] })) };
    const calls = mockFetch({ "/api/v1/work/timesheet": (_url, init) => jsonResponse(init?.method === "POST" ? { ...week, entry: {} } : week) });
    render(<MemoryRouter><TimesheetCard /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Timesheet notes" });
    expect(within(card).getByText("Pump station review")).toBeInTheDocument();
    expect(within(card).getByRole("tab", { name: /Wed 2026-11-18, 1.5 hours/ })).toHaveAttribute("aria-selected", "true");
    await userEvent.type(within(card).getByRole("textbox", { name: "What you worked on" }), "Team meeting 30 min");
    await userEvent.click(within(card).getByRole("button", { name: "Add" }));
    await waitFor(() => expect(calls.some((c) => c.init.method === "POST")).toBe(true));
    const post = calls.find((c) => c.init.method === "POST")!;
    expect(JSON.parse(String(post.init.body))).toEqual({ what: "Team meeting 30 min", hours: null, date: "2026-11-18" });
  });
});
