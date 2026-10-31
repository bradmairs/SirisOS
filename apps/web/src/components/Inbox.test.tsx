import { afterEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { InboxPanel, InboxScreen, applyEvent, resetInbox } from "./Inbox";
import { jsonResponse, mockFetch, signIn, sseResponse } from "../test/helpers";
import type { InboxItem } from "../api/types";

const item = (over: Partial<InboxItem>): InboxItem => ({
  id: "ai:1", origin: "sirisai", kind: "alert", severity: "attention", title: "Something", body: "", source: "siris", app: "SirisAI",
  url: null, link: null, actions: [{ id: "acknowledge", label: "Got it", style: "primary" }], created_at: "2026-10-09T07:00:00Z",
  updated_at: "2026-10-09T07:00:00Z", ...over,
});

const INTRUDER = item({
  id: "ai:7", severity: "urgent", title: "SirisAI: person at front_door", body: "Nobody's home.", source: "intruder_check", link: "cameras",
  actions: [{ id: "lockdown", label: "Lock down", style: "danger", confirm: "Run the lockdown protocol now?" }, { id: "acknowledge", label: "It's fine", style: "secondary" }],
});
const APPROVAL = item({ id: "ai:8", kind: "confirm", title: "Approve: turn on switch.heater", source: "routine 'morning heat'",
  actions: [{ id: "approve", label: "Approve", style: "primary" }, { id: "decline", label: "Decline", style: "secondary" }] });
const APP_DOWN = item({ id: "os:app:archive:down", origin: "sirisos", title: "Engineering Archive is down", body: "Timed out", source: "hub",
  app: "Engineering Archive", url: "https://archive.local", actions: [] });

afterEach(() => resetInbox());

describe("applyEvent", () => {
  it("replaces on snapshot, upserts and removes, urgent first", () => {
    let items = applyEvent([], { type: "snapshot", items: [APPROVAL, APP_DOWN], counts: { open: 2, urgent: 0 } });
    items = applyEvent(items, { type: "upsert", items: [INTRUDER], counts: { open: 3, urgent: 1 } });
    expect(items.map((i) => i.id)).toEqual(["ai:7", "ai:8", "os:app:archive:down"]);
    items = applyEvent(items, { type: "remove", items: [APPROVAL], counts: { open: 2, urgent: 1 } });
    expect(items.map((i) => i.id)).toEqual(["ai:7", "os:app:archive:down"]);
  });
});

describe("<InboxPanel />", () => {
  it("shows the live inbox and acts through SirisOS", async () => {
    signIn();
    const calls = mockFetch({
      "/api/v1/attention/stream": () => sseResponse([
        { type: "snapshot", items: [APPROVAL, APP_DOWN], counts: { open: 2, urgent: 0 } },
        { type: "upsert", items: [INTRUDER], counts: { open: 3, urgent: 1 } },
      ]),
      "/api/v1/attention/ai%3A8/act": () => jsonResponse({ item: { id: "ai:8", status: "done" }, result: { ok: true } }),
      "/api/v1/attention/ai%3A7/act": () => jsonResponse({ item: { id: "ai:7", status: "done" }, result: {} }),
      "/api/v1/attention/os%3Aapp%3Aarchive%3Adown/dismiss": () => jsonResponse({ item: { id: "os:app:archive:down" } }),
      "/api/v1/attention": () => jsonResponse({ items: [], counts: { open: 0, urgent: 0 } }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><InboxPanel /></MemoryRouter>);

    const urgent = await screen.findByRole("listitem", { name: "SirisAI: person at front_door" });
    expect(screen.getByText("1 urgent")).toBeInTheDocument();
    const rows = screen.getAllByRole("listitem").map((li) => li.getAttribute("aria-label"));
    expect(rows[0]).toBe("SirisAI: person at front_door");

    // A guarded action asks first.
    await user.click(within(urgent).getByRole("button", { name: "Lock down" }));
    expect(within(urgent).getByText("Run the lockdown protocol now?")).toBeInTheDocument();
    await user.click(within(urgent).getByRole("button", { name: "Yes" }));
    await waitFor(() => expect(screen.queryByRole("listitem", { name: "SirisAI: person at front_door" })).not.toBeInTheDocument());
    const lockdown = calls.find((c) => c.url.includes("ai%3A7/act"))!;
    expect(JSON.parse(String(lockdown.init.body))).toEqual({ action: "lockdown" });

    await user.click(within(screen.getByRole("listitem", { name: "Approve: turn on switch.heater" })).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("ai%3A8/act"))).toBe(true));

    const down = screen.getByRole("listitem", { name: "Engineering Archive is down" });
    expect(within(down).getByRole("link", { name: /open/i })).toHaveAttribute("href", "https://archive.local");
    await user.click(within(down).getByRole("button", { name: "Dismiss Engineering Archive is down" }));
    await waitFor(() => expect(screen.queryByRole("listitem", { name: "Engineering Archive is down" })).not.toBeInTheDocument());
  });

  it("puts an item back when the action fails", async () => {
    signIn();
    mockFetch({
      "/api/v1/attention/stream": () => sseResponse([{ type: "snapshot", items: [APPROVAL], counts: { open: 1, urgent: 0 } }]),
      "/api/v1/attention/ai%3A8/act": () => jsonResponse({ detail: "SirisAI: That didn't work: heater offline" }, 502),
      "/api/v1/attention": () => jsonResponse({ items: [APPROVAL], counts: { open: 1, urgent: 0 } }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><InboxPanel /></MemoryRouter>);
    const row = await screen.findByRole("listitem", { name: "Approve: turn on switch.heater" });
    await user.click(within(row).getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("heater offline");
    expect(screen.getByRole("listitem", { name: "Approve: turn on switch.heater" })).toBeInTheDocument();
  });
});

describe("slow and dropped actions (6.01)", () => {
  it("keeps the item and says it's still working when SirisAI answers pending", async () => {
    signIn();
    mockFetch({
      "/api/v1/attention/stream": () => sseResponse([{ type: "snapshot", items: [APPROVAL], counts: { open: 1, urgent: 0 } }]),
      "/api/v1/attention/ai%3A8/act": () => jsonResponse({ item: APPROVAL, result: { pending: true, message: "Still working on it; a notice will say how it went." } }),
      "/api/v1/attention": () => jsonResponse({ items: [APPROVAL], counts: { open: 1, urgent: 0 } }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><InboxPanel /></MemoryRouter>);
    const row = await screen.findByRole("listitem", { name: "Approve: turn on switch.heater" });
    await user.click(within(row).getByRole("button", { name: "Approve" }));
    expect(await within(row).findByRole("status")).toHaveTextContent("Still working on it");
    expect(screen.getByRole("listitem", { name: "Approve: turn on switch.heater" })).toBeInTheDocument();
  });

  it("explains a dropped connection instead of 'Load failed'", async () => {
    signIn();
    mockFetch({
      "/api/v1/attention/stream": () => sseResponse([{ type: "snapshot", items: [APPROVAL], counts: { open: 1, urgent: 0 } }]),
      "/api/v1/attention/ai%3A8/act": () => { throw new TypeError("Load failed"); },
      "/api/v1/attention": () => jsonResponse({ items: [APPROVAL], counts: { open: 1, urgent: 0 } }),
    });
    const user = userEvent.setup();
    render(<MemoryRouter><InboxPanel /></MemoryRouter>);
    const row = await screen.findByRole("listitem", { name: "Approve: turn on switch.heater" });
    await user.click(within(row).getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Lost the connection before SirisOS answered");
  });
});

describe("<InboxScreen />", () => {
  it("says so when nothing needs you", async () => {
    signIn();
    mockFetch({
      "/api/v1/attention/stream": () => sseResponse([{ type: "snapshot", items: [], counts: { open: 0, urgent: 0 } }]),
      "/api/v1/attention": () => jsonResponse({ items: [], counts: { open: 0, urgent: 0 } }),
    });
    render(<MemoryRouter><InboxScreen /></MemoryRouter>);
    expect(await screen.findByText("Nothing needs you right now.")).toBeInTheDocument();
  });
});

describe("SirisAI's approval PIN", () => {
  it("asks for it when SirisAI does, and sends it with the action", async () => {
    signIn();
    const UPDATES = item({ id: "ai:9", kind: "suggestion", title: "2 updates waiting on 192.168.0.127", source: "server-updates",
      actions: [{ id: "install", label: "Install updates", style: "primary" }, { id: "later", label: "Not now", style: "secondary" }] });
    const bodies: unknown[] = [];
    mockFetch({
      "/api/v1/attention/stream": () => sseResponse([{ type: "snapshot", items: [UPDATES], counts: { open: 1, urgent: 0 } }]),
      "/api/v1/attention/ai%3A9/act": (_url, init) => {
        const body = JSON.parse(String(init.body));
        bodies.push(body);
        if (!body.pin) return jsonResponse({ detail: "SirisAI: pin_required: approving this needs your PIN" }, 403);
        if (body.pin !== "4321") return jsonResponse({ detail: "SirisAI: Wrong PIN. 4 more and big approvals lock for 10 minutes." }, 403);
        return jsonResponse({ item: { id: "ai:9", status: "done" }, result: null });
      },
    });
    const user = userEvent.setup();
    render(<MemoryRouter><InboxPanel /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Install updates" }));
    const pin = await screen.findByLabelText("Approval PIN", { selector: "input" });
    expect(screen.queryByRole("alert")).toBeNull();  // asking, not an error
    await user.type(pin, "0000");
    await user.click(screen.getByRole("button", { name: "Install updates" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong PIN. 4 more");
    await user.type(screen.getByLabelText("Approval PIN", { selector: "input" }), "4321{enter}");
    await waitFor(() => expect(screen.queryByText("2 updates waiting on 192.168.0.127")).toBeNull());
    expect(bodies).toEqual([{ action: "install" }, { action: "install", pin: "0000" }, { action: "install", pin: "4321" }]);
  });
});
