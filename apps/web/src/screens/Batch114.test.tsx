import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { api, json } from "../api/client";
import { clearResources, useResource } from "../api/resource";
import { failed, flush, keepRequest, pending, retry, startOutbox, waiting } from "../api/outbox";
import { keepNote } from "../api/offlineNotes";
import { brain } from "../api/hub";
import { flightSoon } from "../api/prepare";
import { SyncBar } from "../components/SyncBar";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

beforeEach(() => { startOutbox(); });
afterEach(() => { clearResources(); vi.restoreAllMocks(); localStorage.clear(); });

const down = () => { throw new TypeError("Load failed"); };

function Habits() {
  const res = useResource<{ habits: { id: string; name: string; today: boolean; streak: number }[] }>("mind:habits", () => api("/api/v1/mind/habits"));
  return <ul>{(res.data?.habits ?? []).map((h) => <li key={h.id}>{h.name}: {h.today ? "done" : "not yet"} ({h.streak})</li>)}</ul>;
}

describe("SirisOS 11.4: working offline", () => {
  it("keeps an everyday edit made offline, shows it at once, and sends it when back", async () => {
    signIn();
    mockFetch({ "/api/v1/mind/habits": () => jsonResponse({ habits: [{ id: "h1", name: "Stretch", today: false, streak: 3 }] }) });
    render(<Habits />);
    expect(await screen.findByText("Stretch: not yet (3)")).toBeInTheDocument();
    mockFetch({ "/api": down });
    const out = await api("/api/v1/mind/habits/h1/check", json({ done: true }));
    expect(out).toEqual({ queued: true });
    expect(await screen.findByText("Stretch: done (4)")).toBeInTheDocument();  // shown straight away
    expect(pending()).toHaveLength(1);
    expect(pending()[0]).toMatchObject({ kind: "request", method: "POST", path: "/api/v1/mind/habits/h1/check", label: "A habit" });
    const calls = mockFetch({ "/api/v1/mind/habits/h1/check": () => jsonResponse({ habits: [] }) });
    expect(await flush()).toBe(1);
    expect(waiting()).toBe(0);
    expect(new Headers(calls[0].init.headers).get("X-Sirisos-Replay")).toBe("1");
  });

  it("never queues things that act on the house or run commands", async () => {
    signIn();
    mockFetch({ "/api": down });
    await expect(api("/api/v1/assistant/controls/light.kitchen", json({ on: true }))).rejects.toThrow();
    await expect(api("/api/v1/terminal/run", json({ cmd: "ls" }))).rejects.toThrow();
    expect(waiting()).toBe(0);
  });

  it("keeps what SirisOS said no to for you to retry or let go", async () => {
    signIn();
    keepRequest("PUT", "/api/v1/meals/2026-11-26", JSON.stringify({ title: "Tacos" }), "Meals");
    mockFetch({ "/api/v1/meals": () => jsonResponse({ detail: "That day's gone" }, 422) });
    expect(await flush()).toBe(0);
    expect(waiting()).toBe(0);
    expect(failed()[0]).toMatchObject({ label: "Meals", why: "That day's gone" });
    mockFetch({ "/api/v1/meals": () => jsonResponse({ ok: true }) });
    retry(failed()[0].at);
    await waitFor(() => expect(failed()).toHaveLength(0));
  });

  it("keeps both when a note edited offline changed on the server meanwhile", async () => {
    signIn();
    keepRequest("POST", "/api/v1/brain/edit", JSON.stringify({ title: "Pump station", body: "New text", version: "v1" }), "A Siris note");
    const calls = mockFetch({
      "/api/v1/brain/edit": () => jsonResponse({ detail: "The note changed since you opened it." }, 409),
      "/api/v1/brain/capture": () => jsonResponse({ title: "Pump station (edited offline)" }),
    });
    expect(await flush()).toBe(1);
    const copy = calls.find((c) => c.url.endsWith("/brain/capture"))!;
    expect(JSON.parse(String(copy.init.body)).title).toMatch(/^Pump station \(edited offline \d{4}-\d{2}-\d{2}\)$/);
  });

  it("reads kept Siris notes and searches them with no connection", async () => {
    signIn();
    keepNote({ title: "Culvert sizing", path: "x.md", links: [], backlinks: [], body: "Use the 1% AEP flow for the culvert." });
    mockFetch({ "/api": down });
    expect((await brain.note("Culvert sizing")).body).toContain("1% AEP");
    const hits = await brain.search("culvert flow");
    expect(hits[0].title).toBe("Culvert sizing");
  });

  it("shows offline and what's waiting, and the sheet lists it", async () => {
    signIn();
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    keepRequest("POST", "/api/v1/tasks", JSON.stringify({ text: "x" }), "A task change");
    render(<MemoryRouter><SyncBar /></MemoryRouter>);
    const bar = await screen.findByRole("button", { name: /Offline.*1 waiting/ });
    await userEvent.click(bar);
    expect(screen.getByText("Waiting to sync (1)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Get ready for offline" })).toBeDisabled();  // needs a connection
    await userEvent.click(screen.getByRole("button", { name: "Let go: A task change" }));
    expect(screen.getByText("Waiting to sync (0)")).toBeInTheDocument();
  });

  it("gets ready by itself the day before a trip, not twice", async () => {
    signIn();
    mockFetch({ "/api/v1/travel": () => jsonResponse({ next: { days_to_go: 1 }, upcoming: [], past: [] }) });
    expect(await flightSoon()).toBe(true);
    localStorage.setItem("sirisos.offline.ready", JSON.stringify({ at: Date.now(), screens: 32, notes: 30, failed: [] }));
    expect(await flightSoon()).toBe(false);
  });
});
