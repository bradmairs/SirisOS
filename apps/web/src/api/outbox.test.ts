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
