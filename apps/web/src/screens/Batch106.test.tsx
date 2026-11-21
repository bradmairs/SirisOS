import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { clearResources } from "../api/resource";
import type { Smart } from "../api/push";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { AppPresence, resetSeen, SeenMark } from "../components/Smart";
import { NotificationSettings, SmartSettings } from "../components/NotificationSettings";

afterEach(() => { clearResources(); resetSeen(); vi.restoreAllMocks(); vi.useRealTimers(); localStorage.clear(); });

const body = (c: { init: RequestInit }) => JSON.parse(String(c.init.body));

describe("SirisOS 10.6", () => {
  it("reports a card's notification as seen after two seconds on screen, once", async () => {
    signIn();
    vi.useFakeTimers();
    const calls = mockFetch({ "/api/v1/push/seen": () => jsonResponse({ seen: 1 }) });
    const { rerender } = render(<div><SeenMark k="bins:2026-11-27" /></div>);
    await act(async () => { vi.advanceTimersByTime(1500); });
    expect(calls).toHaveLength(0);
    await act(async () => { vi.advanceTimersByTime(1000); });
    expect(calls.map((c) => c.url)).toEqual(["/api/v1/push/seen"]);
    expect(body(calls[0])).toEqual({ keys: ["bins:2026-11-27"] });
    rerender(<div><SeenMark k="bins:2026-11-27" /><span /></div>);
    await act(async () => { vi.advanceTimersByTime(3000); });
    expect(calls).toHaveLength(1);
  });

  it("says it's open, with this device and a focus block, and shows what came meanwhile as a banner", async () => {
    signIn();
    localStorage.setItem("sirisos.push.device", "abc123-device");
    localStorage.setItem("sirisos.push.endpoint", "https://push.example/mac");
    const ends = Date.now() + 20 * 60_000;
    localStorage.setItem("sirisos.work.focus", JSON.stringify({ mode: "focus", ends, left: 0, sessions: 0, day: "x" }));
    const calls = mockFetch({
      "/api/v1/push/active": () => jsonResponse({ inapp: [{ key: "task:t1", title: "Call the plumber", body: "Before 5", url: "/tasks", at: "x" }] }),
      "/api/v1/push/seen": () => jsonResponse({ seen: 1 }),
    });
    render(<MemoryRouter><AppPresence /></MemoryRouter>);
    expect(await screen.findByText("Call the plumber")).toBeInTheDocument();
    const beat = body(calls[0]);
    expect(beat).toMatchObject({ device: "abc123-device", endpoint: "https://push.example/mac", focus_until: new Date(ends).toISOString() });
    await userEvent.click(screen.getByRole("button", { name: "Dismiss Call the plumber" }));
    expect(screen.queryByText("Call the plumber")).not.toBeInTheDocument();
    await waitFor(() => expect(calls.some((c) => c.url === "/api/v1/push/seen" && body(c).keys[0] === "task:t1")).toBe(true));
  });

  it("lets a banner go by itself after ten seconds", async () => {
    signIn();
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"] });
    localStorage.setItem("sirisos.push.device", "abc123-device");
    const calls = mockFetch({
      "/api/v1/push/active": () => jsonResponse({ inapp: [{ key: "weekend:2026-11-28", title: "Your weekend outside", body: "", url: "/", at: "x" }] }),
      "/api/v1/push/seen": () => jsonResponse({ seen: 1 }),
    });
    render(<MemoryRouter><AppPresence /></MemoryRouter>);
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    expect(screen.getByText("Your weekend outside")).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(10_500); });
    expect(screen.queryByText("Your weekend outside")).not.toBeInTheDocument();
    expect(calls.some((c) => c.url === "/api/v1/push/seen")).toBe(true);
  });

  it("shows the week's notifications by kind and lets each be set", async () => {
    signIn();
    const s: Smart = { on: true, cap: 6, using_now: false, devices: 2, waiting: 1, week: { pushed: 9, opened: 3, ignored: 5, spared: 12 },
      kinds: [{ kind: "catchup", label: "Catch-ups", pushed: 5, opened: 0, ignored: 5, spared: 0, mode: "auto", effective: "roundup", demoted: true, explicit: false },
        { kind: "inbox", label: "Inbox and app alerts", pushed: 4, opened: 3, ignored: 0, spared: 12, mode: "auto", effective: "normal", demoted: false, explicit: false }] };
    const calls = mockFetch({
      "/api/v1/push/smart/kinds/catchup": () => jsonResponse({ ...s, kinds: [{ ...s.kinds[0], mode: "off", effective: "off" }, s.kinds[1]] }),
      "/api/v1/push/smart": () => jsonResponse(s),
    });
    render(<SmartSettings />);
    expect(await screen.findByText(/9 sent, 3 opened, 12 spared, 1 waiting/)).toBeInTheDocument();
    expect(screen.getByText(/moved to the roundup: you weren't opening these/)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Catch-ups: how"), "off");
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/kinds/catchup") && body(c).mode === "off")).toBe(true));
    expect(NotificationSettings).toBeTruthy();
  });
});
