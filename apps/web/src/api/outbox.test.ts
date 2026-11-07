import { afterEach, describe, expect, it } from "vitest";
import { flush, keep, waiting } from "./outbox";
import { jsonResponse, mockFetch, signIn } from "../test/helpers";

afterEach(() => window.localStorage.removeItem("sirisos.outbox"));

describe("outbox (6.3)", () => {
  it("keeps captures made offline and sends them, in order, once SirisOS answers", async () => {
    signIn();
    expect(keep({ kind: "capture", body: { text: "Idea for the culvert" } })).toBe(true);
    expect(keep({ kind: "task", text: "remind me to call Sam" })).toBe(true);
    expect(waiting()).toBe(2);
    // Still unreachable: nothing goes, nothing is lost.
    mockFetch({ "/api/v1/brain/capture": () => { throw new TypeError("Load failed"); } });
    expect(await flush()).toBe(0);
    expect(waiting()).toBe(2);
    const calls = mockFetch({
      "/api/v1/brain/capture": () => jsonResponse({ saved: true, title: "Idea" }),
      "/api/v1/tasks": () => jsonResponse({ id: "t1", title: "Call Sam", due: null, time: null }),
    });
    expect(await flush()).toBe(2);
    expect(waiting()).toBe(0);
    expect(calls.map((c) => c.url)).toEqual(["/api/v1/brain/capture", "/api/v1/tasks"]);
  });

  it("won't keep a big photo", () => {
    expect(keep({ kind: "capture", body: { image: "x".repeat(2_000_000) } })).toBe(false);
  });
});

describe("offline actions (7.6)", () => {
  it("keeps a health log made offline and sends it later", async () => {
    signIn();
    const { health } = await import("./health");
    mockFetch({ "/api/v1/health/log": () => { throw new TypeError("Load failed"); } });
    expect(await health.log("water", 250)).toEqual({ logged: null, queued: true });
    expect(waiting()).toBe(1);
    const calls = mockFetch({ "/api/v1/health/log": () => jsonResponse({ logged: {} }) });
    expect(await flush()).toBe(1);
    expect(JSON.parse(String(calls[0].init.body))).toEqual({ kind: "water", amount: 250, text: "" });
  });

  it("sends a queued dismiss and Got it", async () => {
    signIn();
    expect(keep({ kind: "inbox", id: "ai:4", action: "dismiss" })).toBe(true);
    expect(keep({ kind: "inbox", id: "ai:5", action: "acknowledge" })).toBe(true);
    const calls = mockFetch({
      "/api/v1/attention/ai%3A4/dismiss": () => jsonResponse({ item: { id: "ai:4" } }),
      "/api/v1/attention/ai%3A5/act": () => jsonResponse({ item: { id: "ai:5" }, result: null }),
    });
    expect(await flush()).toBe(2);
    expect(calls.map((c) => c.url)).toEqual(["/api/v1/attention/ai%3A4/dismiss", "/api/v1/attention/ai%3A5/act"]);
  });
});
