import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { TasksScreen } from "./Tasks";
import { WorkScreen } from "./Work";

afterEach(() => { clearResources(); vi.restoreAllMocks(); window.localStorage.removeItem("sirisos.work.focus"); });

const DAY = {
  date: "2026-11-05", local_time: "2026-11-05T10:00+11:00",
  hours: { start: "08:00", end: "16:30", on: true, workday: true, minutes_left: 390, minutes_in: 120 },
  tasks: { groups: { overdue: [], today: [], week: [] }, counts: { overdue: 0, today: 0, week: 0 } },
  todos: [], engineering: { current: null, active: [] }, cpd: null,
  apps: [{ id: "a", name: "Timesheet", url: "https://t.example", icon: null, note: "" }],
  settings: { focus_min: 50, break_min: 10, apps: null, calculators: true, career: true },
};
const LINKS = { groups: [{ id: "g", name: "Tools", links: [{ id: "a", name: "Timesheet", url: "https://t.example" }, { id: "b", name: "Maps", url: "https://m.example" }] }] };

describe("Tasks are for today unless you say (8.21)", () => {
  it("adds without a date as today, and a changed or cleared date goes with it", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/tasks": (_url, init) => init?.method === "POST" ? jsonResponse({ id: "t", title: "Buy milk", due: null, time: null, repeat: "none" })
      : jsonResponse({ tasks: [], groups: {}, counts: { overdue: 0, today: 0, week: 0, later: 0, someday: 0 }, sources: {} }) });
    render(<MemoryRouter><TasksScreen /></MemoryRouter>);
    const box = await screen.findByLabelText("Add a task");
    await userEvent.type(box, "Buy milk{enter}");
    await vi.waitFor(() => expect(calls.filter((c) => c.init.method === "POST")).toHaveLength(1));
    expect(JSON.parse(String(calls.find((c) => c.init.method === "POST")!.init.body))).toEqual({ text: "Buy milk" });
    fireEvent.change(screen.getByLabelText(/Due \(clear it/), { target: { value: "" } });
    await userEvent.type(box, "Read a book{enter}");
    await vi.waitFor(() => expect(calls.filter((c) => c.init.method === "POST")).toHaveLength(2));
    expect(JSON.parse(String(calls.filter((c) => c.init.method === "POST")[1].init.body))).toEqual({ text: "Read a book", due: null });
  });
});

describe("Work settings (8.21)", () => {
  it("runs the focus timer at your length and saves a new one", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/work/settings": () => jsonResponse({ ...DAY.settings, focus_min: 40 }), "/api/v1/work": () => jsonResponse(DAY), "/api/v1/links/status": () => jsonResponse({}) });
    render(<MemoryRouter><WorkScreen /></MemoryRouter>);
    expect(await screen.findByText("50:00")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Change the focus and break times" }));
    const focus = screen.getByLabelText("Focus minutes");
    await userEvent.clear(focus);
    await userEvent.type(focus, "40");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(calls.find((c) => c.url.endsWith("/work/settings"))?.init.body).toContain('"focus_min":40'));
    expect(await screen.findByText("40:00")).toBeInTheDocument();
  });

  it("picks the apps, in order, and goes back to automatic", async () => {
    signIn();
    const calls = mockFetch({ "/api/v1/work/settings": () => jsonResponse(DAY.settings), "/api/v1/links/status": () => jsonResponse({}), "/api/v1/links": () => jsonResponse(LINKS), "/api/v1/work": () => jsonResponse(DAY) });
    render(<MemoryRouter><WorkScreen /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    await userEvent.click(await screen.findByRole("checkbox", { name: "Maps" }));
    await userEvent.click(screen.getByRole("button", { name: "Move Maps up" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Career" }));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(calls.some((c) => c.url.endsWith("/work/settings"))).toBe(true));
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/work/settings"))!.init.body))).toEqual({ apps: ["b", "a"], calculators: true, career: false });
  });
});
