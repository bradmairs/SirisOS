import { describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { TasksScreen } from "./Tasks";
import { TasksWidget } from "./TasksWidget";
import type { TaskItem, TaskList } from "../api/tasks";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

const iso = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const item = (over: Partial<TaskItem>): TaskItem => ({ id: "sirisos:a", source: "sirisos", title: "x", detail: null, due: null, time: null, repeat: "none", group: "someday", ...over });

function listOf(items: TaskItem[]): TaskList {
  const groups = { overdue: [], today: [], week: [], later: [], someday: [] } as TaskList["groups"];
  items.forEach((t) => groups[t.group].push(t));
  return { date: iso(0), groups, counts: Object.fromEntries(Object.entries(groups).map(([k, v]) => [k, v.length])) as TaskList["counts"] };
}

const LIST = listOf([
  item({ id: "siris:Werribee Drainage|Send levels to Dana", source: "siris", title: "Send levels to Dana", detail: "Werribee Drainage", note: "Werribee Drainage", due: iso(-2), group: "overdue" }),
  item({ id: "sirisos:bins", title: "Put the bins out", due: iso(0), time: "19:00", group: "today" }),
  item({ id: "reminder:7", source: "reminder", title: "Call Mum", detail: "SirisAI reminder", due: iso(0), time: "20:00", group: "today" }),
  item({ id: "sirisos:cpd", title: "Log CPD", due: iso(3), repeat: "weekly", group: "week" }),
  item({ id: "sirisos:garden", title: "Plan the garden" }),
]);

describe("<TasksScreen />", () => {
  it("groups every task, adds one from plain words and ticks one off", async () => {
    signIn();
    let served = LIST;
    const calls = mockFetch({
      "/api/v1/tasks/siris": () => {
        served = listOf(Object.values(LIST.groups).flat().filter((t) => t.source !== "siris"));
        return jsonResponse({ id: "siris:…", action: "done" });
      },
      "/api/v1/tasks": (_u, init) => (init.method === "POST" ? jsonResponse({ id: "n", title: "Pay rego", due: iso(2), time: null, repeat: "none" }) : jsonResponse(served)),
    });
    const user = userEvent.setup();
    render(<TasksScreen />);
    expect(await screen.findByText("3 for today")).toBeInTheDocument();
    const overdue = screen.getByRole("region", { name: "Overdue" });
    expect(within(overdue).getByText("Send levels to Dana")).toBeInTheDocument();
    expect(within(overdue).getByText(/2 days late · Werribee Drainage/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Today" })).getByText(/Today · 19:00/)).toBeInTheDocument();
    expect(screen.getByLabelText("Repeats weekly")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete Send levels to Dana" })).not.toBeInTheDocument();  // lives in a note

    await user.type(screen.getByLabelText("Add a task"), "pay rego friday");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Added “Pay rego”");
    expect(JSON.parse(String(calls.find((c) => c.init.method === "POST")!.init.body))).toEqual({ text: "pay rego friday" });

    await user.click(screen.getByRole("button", { name: "Done: Send levels to Dana" }));
    await waitFor(() => expect(screen.queryByText("Send levels to Dana")).not.toBeInTheDocument());
    const done = calls.find((c) => c.url.includes("/done"))!;
    expect(done.url).toBe("/api/v1/tasks/siris%3AWerribee%20Drainage%7CSend%20levels%20to%20Dana/done");
    expect(JSON.parse(String(done.init.body))).toEqual({ note: "Werribee Drainage", title: "Send levels to Dana" });
  });

  it("snoozes a task to tomorrow", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/tasks/sirisos%3Abins/snooze": () => jsonResponse({ id: "sirisos:bins", snoozed_until: iso(1) }),
      "/api/v1/tasks": () => jsonResponse(LIST),
    });
    const user = userEvent.setup();
    render(<TasksScreen />);
    await user.click(await screen.findByRole("button", { name: "Snooze Put the bins out" }));
    await user.click(within(screen.getByRole("group", { name: "Snooze Put the bins out" })).getByRole("button", { name: "Tomorrow" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Snoozed “Put the bins out” to tomorrow");
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/snooze"))!.init.body))).toEqual({ until: "tomorrow" });
  });

  it("says when there's nothing to do", async () => {
    signIn();
    mockFetch({ "/api/v1/tasks": () => jsonResponse(listOf([])) });
    render(<TasksScreen />);
    expect(await screen.findByText(/No tasks/)).toBeInTheDocument();
  });
});

describe("<TasksWidget />", () => {
  it("shows what's due today and links to the rest", async () => {
    signIn();
    mockFetch({ "/api/v1/tasks": () => jsonResponse(LIST) });
    render(<MemoryRouter><TasksWidget /></MemoryRouter>);
    expect(await screen.findByText("Send levels to Dana")).toBeInTheDocument();
    expect(screen.getByText("Call Mum")).toBeInTheDocument();
    expect(screen.queryByText("Plan the garden")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "All tasks" })).toHaveAttribute("href", "/tasks");
  });
});
