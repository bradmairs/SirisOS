import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";
import { deviceId, push, syncPush } from "./push";
import { NotificationSettings } from "../components/NotificationSettings";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.removeItem("sirisos.push.endpoint"); });

const keys = { p256dh: "k".repeat(20), auth: "a".repeat(10) };
const device = (endpoint: string, created: string, extra = {}) => ({ endpoint, label: "iPhone", topics: ["inbox"], created_at: created, ...extra });

describe("one install, one device (7.9)", () => {
  it("sends this install's id, and the endpoint it replaces", async () => {
    signIn();
    localStorage.setItem("sirisos.push.endpoint", "https://web.push.apple.com/old");
    const calls = mockFetch({ "/api/v1/push/subscribe": (_u, init) => jsonResponse({ ...JSON.parse(String(init.body)), created_at: "x" }) });
    await push.subscribe({ endpoint: "https://web.push.apple.com/new", keys }, "iPhone", ["inbox"]);
    const sent = JSON.parse(String(calls[0].init.body));
    expect(sent).toMatchObject({ endpoint: "https://web.push.apple.com/new", device: deviceId(), replaces: "https://web.push.apple.com/old" });
    expect(deviceId()).toBe(deviceId());  // kept
    expect(localStorage.getItem("sirisos.push.endpoint")).toBe("https://web.push.apple.com/new");
  });

  it("re-registers on opening when the subscription changed, keeping its topics", async () => {
    signIn();
    localStorage.setItem("sirisos.push.endpoint", "https://web.push.apple.com/old");
    vi.stubGlobal("Notification", { permission: "granted" });
    const sub = { endpoint: "https://web.push.apple.com/renewed", toJSON: () => ({ endpoint: "https://web.push.apple.com/renewed", keys }) };
    Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { getRegistration: async () => ({ pushManager: { getSubscription: async () => sub } }) } });
    vi.stubGlobal("PushManager", function PushManager() {});
    const calls = mockFetch({
      "/api/v1/push/subscriptions": () => jsonResponse({ subscriptions: [device("https://web.push.apple.com/old", "2026-10-01", { topics: ["inbox", "gym"] })] }),
      "/api/v1/push/subscribe": (_u, init) => jsonResponse({ ...JSON.parse(String(init.body)), created_at: "x" }),
    });
    await syncPush();
    const sent = JSON.parse(String(calls.find((c) => c.url.endsWith("/subscribe"))!.init.body));
    expect(sent).toMatchObject({ endpoint: "https://web.push.apple.com/renewed", replaces: "https://web.push.apple.com/old", topics: ["inbox", "gym"] });
  });
});

describe("devices getting notifications (7.9)", () => {
  it("lists them and removes the old copy of this phone", async () => {
    signIn();
    vi.stubGlobal("Notification", { permission: "granted" });
    const sub = { endpoint: "https://web.push.apple.com/now", toJSON: () => ({}) };
    Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { getRegistration: async () => ({ pushManager: { getSubscription: async () => sub } }) } });
    vi.stubGlobal("PushManager", function PushManager() {});
    let list = [device("https://web.push.apple.com/old", "2026-09-01T00:00:00Z"), device("https://web.push.apple.com/now", "2026-11-07T00:00:00Z")];
    const calls = mockFetch({
      "/api/v1/push/subscriptions": () => jsonResponse({ subscriptions: list }),
      "/api/v1/push/unsubscribe": (_u, init) => { list = list.filter((d) => d.endpoint !== JSON.parse(String(init.body)).endpoint); return jsonResponse({ removed: true }); },
    });
    const user = userEvent.setup();
    render(<NotificationSettings />);
    expect(await screen.findByText(/listed more than once/)).toBeInTheDocument();
    expect(screen.getByText("iPhone (this device)")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove iPhone added 2026-09-01" }));
    expect(JSON.parse(String(calls.find((c) => c.url.endsWith("/unsubscribe"))!.init.body))).toEqual({ endpoint: "https://web.push.apple.com/old" });
    await vi.waitFor(() => expect(screen.queryByText(/listed more than once/)).not.toBeInTheDocument());
  });
});
