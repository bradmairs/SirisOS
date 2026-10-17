import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NotificationSettings } from "./NotificationSettings";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

function stubPush() {
  const subscription = {
    endpoint: "https://push.example.com/abc",
    toJSON: () => ({ endpoint: "https://push.example.com/abc", keys: { p256dh: "p".repeat(20), auth: "a".repeat(12) } }),
    unsubscribe: vi.fn(async () => true),
  };
  let current: typeof subscription | null = null;
  const pushManager = { getSubscription: vi.fn(async () => current), subscribe: vi.fn(async () => (current = subscription)) };
  const registration = { pushManager };
  vi.stubGlobal("PushManager", function PushManager() {});
  vi.stubGlobal("Notification", { requestPermission: vi.fn(async () => "granted") });
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { getRegistration: vi.fn(async () => registration), register: vi.fn(async () => registration), ready: Promise.resolve(registration) },
  });
  return { pushManager, subscription };
}

afterEach(() => {
  vi.unstubAllGlobals();
  // jsdom has no service worker; take ours away again.
  delete (navigator as unknown as Record<string, unknown>).serviceWorker;
});

describe("<NotificationSettings />", () => {
  it("explains Add to Home Screen on an iPhone browser tab", async () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)");
    render(<NotificationSettings />);
    expect(await screen.findByText(/add SirisOS to your Home Screen first/)).toBeInTheDocument();
  });

  it("turns notifications on with the chosen topics, sends a test and turns off", async () => {
    signIn();
    const { pushManager, subscription } = stubPush();
    const calls = mockFetch({
      "/api/v1/push/key": () => jsonResponse({ public_key: "BKz0", topics: ["apps", "inbox", "brief", "career"] }),
      "/api/v1/push/subscriptions": () => jsonResponse({ subscriptions: [] }),
      "/api/v1/push/subscribe": (_u, init) => {
        const body = JSON.parse(String(init?.body));
        return jsonResponse({ endpoint: body.endpoint, label: body.label, topics: body.topics, created_at: "" });
      },
      "/api/v1/push/test": () => jsonResponse({ sent: true }),
      "/api/v1/push/unsubscribe": () => jsonResponse({ removed: true }),
    });
    const user = userEvent.setup();
    render(<NotificationSettings />);
    await user.click(await screen.findByLabelText("Your daily brief is ready"));
    await user.click(screen.getByRole("button", { name: /Turn on notifications/ }));
    expect(await screen.findByRole("button", { name: /Send a test/ })).toBeInTheDocument();
    expect(pushManager.subscribe).toHaveBeenCalledWith(expect.objectContaining({ userVisibleOnly: true }));
    const sent = JSON.parse(String(calls.find((c) => c.url.endsWith("/subscribe"))!.init.body));
    expect(sent.topics).toEqual(["apps", "inbox", "career"]);
    expect(sent.keys.auth).toBe("a".repeat(12));

    await user.click(screen.getByRole("button", { name: /Send a test/ }));
    expect(await screen.findByText(/Sent\./)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Turn off/ }));
    expect(await screen.findByRole("button", { name: /Turn on notifications/ })).toBeInTheDocument();
    expect(subscription.unsubscribe).toHaveBeenCalled();
  });
});
