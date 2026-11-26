import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import { InboxPanel, isUpkeep, resetInbox } from "../components/Inbox";
import type { InboxItem } from "../api/types";
import { jsonResponse, mockFetch, signIn, sseResponse } from "../test/helpers";
import { HandbookScreen } from "./Handbook";
import { HabitsView } from "./HealthMind";

const item = (over: Partial<InboxItem>): InboxItem => ({
  id: "ai:1", origin: "sirisai", kind: "alert", severity: "attention", title: "Something", body: "", source: "siris", app: "SirisAI",
  url: null, link: null, actions: [{ id: "acknowledge", label: "Got it", style: "primary" }], created_at: "2026-11-26T07:00:00Z",
  updated_at: "2026-11-26T07:00:00Z", ...over,
});

afterEach(() => { clearResources(); resetInbox(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("SirisOS 11.10", () => {
  it("folds SirisAI's own upkeep notices into one line on Home, and clears them together", async () => {
    signIn();
    const date = item({ id: "ai:2", source: "upkeep", title: "SirisAI answered a date question wrong" });
    const plex = item({ id: "ai:3", source: "upkeep", title: "SirisAI answered a plex question wrong" });
    const real = item({ id: "ai:4", source: "bills", title: "Electricity bill due Friday" });
    const urgent = item({ id: "ai:5", source: "upkeep", severity: "urgent", title: "The disk is full" });
    expect([date, real, urgent].map(isUpkeep)).toEqual([true, false, false]);
    const calls = mockFetch({
      "/api/v1/attention/stream": () => sseResponse([{ type: "snapshot", items: [date, plex, real, urgent], counts: { open: 4, urgent: 1 } }]),
      "/api/v1/attention/ai%3A2/act": () => jsonResponse({ item: { id: "ai:2", status: "done" }, result: {} }),
      "/api/v1/attention/ai%3A3/act": () => jsonResponse({ item: { id: "ai:3", status: "done" }, result: {} }),
      "/api/v1/attention": () => jsonResponse({ items: [date, plex, real, urgent], counts: { open: 4, urgent: 1 } }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><InboxPanel /></MemoryRouter>);
    const panel = await screen.findByRole("region", { name: "Needs you" });
    expect(await within(panel).findByText("Electricity bill due Friday")).toBeInTheDocument();
    expect(within(panel).getByText("The disk is full")).toBeInTheDocument();  // urgent: never folded
    expect(within(panel).queryByText("SirisAI answered a date question wrong")).toBeNull();
    expect(within(panel).getByText(/SirisAI upkeep: 2 things/)).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Got it, all of them" }));
    await waitFor(() => expect(calls.filter((c) => c.url.includes("/act")).map((c) => c.url)).toEqual(["/api/v1/attention/ai%3A2/act", "/api/v1/attention/ai%3A3/act"]));
  });

  it("edits a habit: name and days, then moves and brings back a stopped one", async () => {
    signIn();
    const habit = (id: string, name: string) => ({ id, name, created: "2026-11-01", streak: 2, best: 5, today: false, rate: 50, days: [], month: [] });
    const calls = mockFetch({
      "/api/v1/mind/habits/h1": (_u, init) => jsonResponse({ habits: [{ ...habit("h1", JSON.parse(String(init?.body)).name ?? "Read") }], stopped: [{ id: "h9", name: "Walk", days_done: 12 }] }),
      "/api/v1/mind/habits/h9": () => jsonResponse({ habits: [habit("h1", "Read"), habit("h9", "Walk")], stopped: [] }),
      "/api/v1/mind/habits": () => jsonResponse({ habits: [habit("h1", "Read")], stopped: [{ id: "h9", name: "Walk", days_done: 12 }] }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><HabitsView /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Edit Read" }));
    const form = screen.getByRole("form", { name: "Edit Read" });
    const name = within(form).getByRole("textbox", { name: "Habit name" });
    await user.clear(name);
    await user.type(name, "Read 20 pages");
    await user.click(within(form).getByRole("button", { name: "Save" }));
    const sent = calls.find((c) => c.url.endsWith("/habits/h1") && c.init.method === "PATCH");
    expect(JSON.parse(String(sent?.init.body))).toEqual({ name: "Read 20 pages", days: [] });
    await user.click(screen.getByRole("button", { name: "Stopped habits (1)" }));
    await user.click(screen.getByRole("button", { name: "Bring back" }));
    const back = calls.find((c) => c.url.endsWith("/habits/h9"));
    expect(JSON.parse(String(back?.init.body))).toEqual({ archived: false });
  });

  it("searches the handbook and copies a command", async () => {
    signIn();
    mockFetch({ "/api/v1/handbook": () => jsonResponse({ entries: [{ id: "e1", cmd: "ssh me@box", what: "My box", section: "Mine" }] }) });
    const user = userEvent.setup();  // before the clipboard: it puts in its own
    const write = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText: write }, configurable: true });
    render(<MemoryRouter><HandbookScreen /></MemoryRouter>);
    await user.type(screen.getByRole("searchbox", { name: "Search the handbook" }), "nvidia");
    const gpu = await screen.findByRole("region", { name: "The GPU and the local AI" });
    expect(screen.queryByRole("region", { name: "Docker" })).toBeNull();
    await user.click(within(gpu).getByRole("button", { name: "Copy nvidia-smi" }));
    expect(write).toHaveBeenCalledWith("nvidia-smi");
    await user.clear(screen.getByRole("searchbox", { name: "Search the handbook" }));
    await user.click(await screen.findByRole("button", { name: /Mine/ }));
    expect(screen.getByText("ssh me@box")).toBeInTheDocument();
  });
});
