import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { WorkHomeCard, WorkScreen } from "./Work";
import { dayFraction } from "../api/work";

afterEach(() => { clearResources(); vi.restoreAllMocks(); });

const DAY = {
  date: "2026-11-05", local_time: "2026-11-05T10:00+11:00",
  hours: { start: "08:00", end: "16:30", on: true, workday: true, minutes_left: 390, minutes_in: 120 },
  events: [{ title: "Design review", start: "2026-11-05T11:00:00+11:00", end: "2026-11-05T12:00:00+11:00", all_day: false, location: "Shepparton" },
    { title: "Site visit", start: "2026-11-05T14:00:00+11:00", end: null, all_day: false, location: null }],
  next: { title: "Design review", start: "2026-11-05T11:00:00+11:00", end: "2026-11-05T12:00:00+11:00", all_day: false, location: "Shepparton", in_minutes: 60, now: false },
  tasks: { groups: { overdue: [], today: [{ id: "sirisos:t1", source: "sirisos", title: "Check the pump station drawings", detail: null, due: "2026-11-05", time: null, group: "today", area: "work" }], week: [] },
    counts: { overdue: 0, today: 1, week: 0 } },
  projects: [{ title: "GVW Sewer Upgrade", due: "2026-11-20", days_left: 15, open_tasks: 1 }],
  todos: [{ task: "Issue RFI 3", note: "GVW Sewer Upgrade", due: "2026-11-07" }],
  engineering: { current: { id: "p1", name: "Mooroopna pump station", kind: "water", tags: [] }, active: [] },
  cpd: { total: 112, required: 150, short: 38 },
};

describe("Work (7.2)", () => {
  it("brings the working day together and ticks off work tasks and note to-dos", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/work": () => jsonResponse(DAY),
      "/api/v1/tasks/": () => jsonResponse({ id: "t1", action: "done" }),
      "/api/v1/tasks": () => jsonResponse({ id: "t2", title: "Send RFI", due: null, time: null, repeat: "none" }),
      "/api/v1/brain/done": () => jsonResponse({ action: "done", note: "GVW Sewer Upgrade", task: "Issue RFI 3" }),
      "/api/v1/brain/capture": () => jsonResponse({ saved: true, title: "Pump curve check" }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><WorkScreen /></MemoryRouter>);
    expect(await screen.findByText("Home time in 6 h 30 min (16:30)")).toBeInTheDocument();
    // 7.31: no calendar (not linked for work) and no projects (Projects is personal).
    expect(screen.queryByText("Design review")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Work projects" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Meetings today" })).not.toBeInTheDocument();
    expect(screen.getByText(/Engineering project:/)).toHaveTextContent("Mooroopna pump station");
    expect(screen.getByRole("img", { name: "CPD: 112 of 150 hours in three years" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Done: Check the pump station drawings" }));
    await vi.waitFor(() => expect(calls.some((c) => c.url.includes("/api/v1/tasks/sirisos%3At1/done"))).toBe(true));
    await user.click(screen.getByRole("button", { name: "Done: Issue RFI 3" }));
    await vi.waitFor(() => expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/brain/done"))!.init.body))).toEqual({ note: "GVW Sewer Upgrade", task: "Issue RFI 3" }));
    await user.type(screen.getByLabelText("New work task"), "Send RFI tomorrow");
    await user.click(screen.getByRole("button", { name: "Add" }));
    await vi.waitFor(() => expect(JSON.parse(String(calls.find((c) => c.url === "/api/v1/tasks")!.init.body))).toEqual({ text: "Send RFI tomorrow", area: "work" }));
    await user.type(screen.getByLabelText("Work note"), "Pump curve check");
    await user.click(screen.getByRole("button", { name: "Save to Siris" }));
    expect(await screen.findByText("Saved to Siris as “Pump curve check”.")).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/brain/capture"))!.init.body)).tags).toEqual(["work"]);
  });

  it("shows on Home only in work hours", async () => {
    signIn();
    mockFetch({ "/api/v1/work": () => jsonResponse(DAY) });
    render(<MemoryRouter><WorkHomeCard /></MemoryRouter>);
    expect(await screen.findByText("At work")).toBeInTheDocument();
    expect(screen.getByText("1 work task due · 1 to-do in work notes")).toBeInTheDocument();
    clearResources();
    mockFetch({ "/api/v1/work": () => jsonResponse({ ...DAY, hours: { ...DAY.hours, on: false, minutes_left: null } }) });
    const off = render(<MemoryRouter><WorkHomeCard /></MemoryRouter>);
    await new Promise((r) => setTimeout(r, 20));
    expect(off.container).toBeEmptyDOMElement();
  });
});


const RICH = {
  ...DAY,
  tasks: { groups: { overdue: [{ id: "sirisos:o", source: "sirisos", title: "Return the RFI", detail: null, due: "2026-11-04", time: null, group: "overdue", area: "work" }],
    today: DAY.tasks.groups.today, week: [] }, counts: { overdue: 1, today: 1, week: 0 } },
  cpd: { total: 112, required: 150, short: 38, minimums: [{ category: "risk", label: "Risk management", hours: 6.5, minimum: 10, short: 3.5 }] },
  week: { days: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d, i) => ({ date: `2026-11-0${2 + i}`, weekday: d, done: [3, 5, 2, 4, 1, 0, 0][i], focus_min: 25 })),
    done_today: 4, focus_today: 75 },
  apps: [{ id: "l1", name: "GVW", url: "https://gvw.sirishome.org", icon: null, note: "" }],
  notes: [{ title: "Pump Station Design", path: "Work/GVW/Pump Station Design.md", type: "note", as_of: "2026-11-04", tags: [], excerpt: "Duty/standby submersibles." }],
};

describe("Work, visual (7.4)", () => {
  it("shows the day, task tiles, the week's bars, app tiles, CPD rings and recent work notes", async () => {
    signIn();
    mockFetch({ "/api/v1/links/status": () => jsonResponse({ l1: { up: true, status: 200, ms: 20 } }), "/api/v1/work": () => jsonResponse(RICH) });
    const user = userEvent.setup();
    render(<MemoryRouter><WorkScreen /></MemoryRouter>);
    expect(await screen.findByText("1h 15m")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /1\s*Overdue/ })).toHaveAttribute("aria-selected", "true");  // overdue first when there is some
    expect(screen.getByText("Return the RFI")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /1\s*Today/ }));
    expect(screen.getByText("Check the pump station drawings")).toBeInTheDocument();
    expect(screen.getByRole("listitem", { name: "Tue: 5 done, 25 min focused" })).toBeInTheDocument();
    const apps = screen.getByRole("region", { name: "Work apps" });
    expect(within(apps).getByRole("link", { name: /^GVW/ })).toHaveAttribute("href", "https://gvw.sirishome.org");
    expect(within(apps).getByRole("link", { name: "Calculators" })).toHaveAttribute("href", "/engineering");
    expect(await screen.findByLabelText("Up")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Risk management: 6.5 of 10 hours" })).toBeInTheDocument();
    expect(screen.getByText("3.5 h short")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Pump Station Design/ })).toHaveAttribute("href", "/brain?q=Pump%20Station%20Design");
  });

  it("logs CPD in a category and shows the new totals", async () => {
    signIn();
    const after = { ...RICH.cpd, total: 113.5, minimums: [{ category: "risk", label: "Risk management", hours: 8, minimum: 10, short: 2 }] };
    let logged = false;
    const calls = mockFetch({
      "/api/v1/work/cpd": () => { logged = true; return jsonResponse({ record: {}, cpd: after }); },
      "/api/v1/work": () => jsonResponse(logged ? { ...RICH, cpd: after } : RICH),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><WorkScreen /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Log CPD" }));
    await user.type(screen.getByLabelText("CPD activity"), "Safety in design webinar");
    await user.click(screen.getByRole("radio", { name: "Risk" }));
    await user.clear(screen.getByLabelText("Hours"));
    await user.type(screen.getByLabelText("Hours"), "1.5");
    await user.click(screen.getByRole("button", { name: "Log it" }));
    expect(await screen.findByText(/Logged 1.5 h of risk/)).toBeInTheDocument();
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/work/cpd"))!.init.body))).toEqual({ title: "Safety in design webinar", hours: 1.5, category: "risk" });
    expect(screen.getByText("2 h short")).toBeInTheDocument();
  });

  it("runs a 25-minute focus block and logs it when it ends", async () => {
    signIn();
    window.localStorage.removeItem("sirisos.work.focus");
    const calls = mockFetch({ "/api/v1/work/focus": () => jsonResponse({ today: 25 }), "/api/v1/work": () => jsonResponse(RICH) });
    render(<MemoryRouter><WorkScreen /></MemoryRouter>);
    const start = await screen.findByRole("button", { name: "Start" });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      start.click();
      await vi.advanceTimersByTimeAsync(25 * 60 * 1000 + 1000);
      await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/work/focus"))).toBe(true));
      expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/work/focus"))!.init.body))).toEqual({ minutes: 25 });
      expect(await screen.findByText("1 done today")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
      window.localStorage.removeItem("sirisos.work.focus");
    }
  });

  it("knows how far through the working day it is", () => {
    expect(dayFraction("08:00", "16:30", new Date(2026, 10, 6, 7, 0))).toBe(0);
    expect(dayFraction("08:00", "16:30", new Date(2026, 10, 6, 12, 15))).toBeCloseTo(0.5, 2);
    expect(dayFraction("08:00", "16:30", new Date(2026, 10, 6, 17, 0))).toBe(1);
  });
});

describe("Work wrap-up, chartership and asking about the page (7.5)", () => {
  const WRAP = { ...DAY, hours: { ...DAY.hours, minutes_left: 10 },
    wrapup: { due: true, saved: null, next_workday: "2026-11-06" },
    chartership: { now: { percent: 50, solid: 2, elements: 16, evidence: 13 }, change: { percent: 13, solid: 1, since: "2026-10-08" },
      trend: [{ week: "2026-10-05", percent: 37, solid: 1, elements: 16, evidence: 6 }, { week: "2026-11-02", percent: 50, solid: 2, elements: 16, evidence: 13 }],
      next: "Add a second piece of evidence", weakest: [{ id: "1.1", title: "Personal commitment", strength: "none" }] } };

  it("wraps up work: what got done, tasks carried to the next workday, first thing, CPD", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/work/wrapup": () => jsonResponse({ done: "Finished the RFI response.", carried: 1, first: "Call the contractor", note: "", cpd: {}, saved_as: "memories", next_workday: "2026-11-06", at: "2026-11-05T16:25+11:00" }),
      "/api/v1/work": () => jsonResponse(WRAP),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><WorkScreen /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Work wrap-up" });
    expect(within(card).getByText("Carry over to Friday")).toBeInTheDocument();
    expect(within(card).getByRole("checkbox", { name: "Check the pump station drawings" })).toBeChecked();
    await user.type(within(card).getByPlaceholderText(/Finished the RFI/), "Finished the RFI response.");
    await user.type(within(card).getByPlaceholderText(/Call the contractor/), "Call the contractor");
    await user.type(within(card).getByLabelText("CPD activity"), "Toolbox talk");
    await user.click(within(card).getByRole("radio", { name: "Risk" }));
    await user.click(within(card).getByRole("button", { name: "Done for the day" }));
    await vi.waitFor(() => expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/work/wrapup"))!.init.body))).toEqual({
      done: "Finished the RFI response.", carry: ["sirisos:t1"], first: "Call the contractor", note: "", cpd: { title: "Toolbox talk", hours: 1, category: "risk" } }));
  });

  it("shows chartership progress and its trend, and hands the page to Siris", async () => {
    signIn();
    mockFetch({ "/api/v1/work": () => jsonResponse({ ...WRAP, wrapup: { due: false, saved: null, next_workday: "2026-11-06" } }) });
    render(<MemoryRouter><WorkScreen /></MemoryRouter>);
    const card = await screen.findByRole("region", { name: "Chartership" });
    expect(within(card).getByRole("img", { name: "Application 50% ready" })).toBeInTheDocument();
    expect(within(card).getByText(/\+13% since/)).toBeInTheDocument();
    expect(within(card).getByRole("img", { name: /Readiness by week/ })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Work wrap-up" })).not.toBeInTheDocument();
    const { pageContext, withContext } = await import("../api/pageContext");
    const ctx = pageContext();
    expect(ctx?.title).toBe("Work");
    expect(ctx?.summary).toContain("Work tasks due today: Check the pump station drawings.");
    expect(withContext("What should I focus on?", ctx)).toMatch(/^What should I focus on\?\n\n\(Asked from SirisOS's Work page\. What's on it now:\nWorking hours/);
  });
});
