import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { WorkHomeCard, WorkScreen } from "./Work";

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
    expect(screen.getByText(/Working on/)).toHaveTextContent("Mooroopna pump station");
    expect(screen.getByText(/CPD: 112 of 150 hours/)).toBeInTheDocument();
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
