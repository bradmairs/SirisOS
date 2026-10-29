import { describe, expect, it } from "vitest";
import { dockBadges, dockItems } from "./Dock";

const labels = (ctx: Parameters<typeof dockItems>[0], adapt = true) => dockItems(ctx, adapt).map((n) => n.label);

describe("the tab bar", () => {
  it("keeps Home, SirisAI and Siris first, always", () => {
    for (const phase of ["morning", "work", "weekend", "evening", "winddown", "night"] as const) {
      expect(labels({ phase, home: true }).slice(0, 3)).toEqual(["Home", "SirisAI", "Siris"]);
    }
  });

  it("makes the fourth the brief in the morning, Wrap up from wind down, Links otherwise", () => {
    expect(labels({ phase: "morning", home: true })[3]).toBe("Brief");
    expect(labels({ phase: "winddown", home: true })[3]).toBe("Wrap up");
    expect(labels({ phase: "night", home: true })[3]).toBe("Wrap up");
    expect(labels({ phase: "work", home: true })[3]).toBe("Links");
    expect(labels({ phase: "evening", home: true })[3]).toBe("Links");
  });

  it("makes the fifth Career at work, Smart home at home, Tasks out, Career when it can't tell", () => {
    expect(labels({ phase: "work", home: true })[4]).toBe("Career");     // even working from home
    expect(labels({ phase: "evening", home: true })[4]).toBe("Smart home");
    expect(labels({ phase: "weekend", home: false })[4]).toBe("Tasks");
    expect(labels({ phase: "evening", home: null })[4]).toBe("Career");
  });

  it("uses what you picked in Times of day over the automatic choice", () => {
    expect(labels({ phase: "evening", home: true, dock: { fourth: "/review", fifth: "auto" } })).toEqual(["Home", "SirisAI", "Siris", "Review", "Smart home"]);
    expect(labels({ phase: "work", home: true, dock: { fourth: "auto", fifth: "/engineering" } })[4]).toBe("Engineering");
    expect(labels({ phase: "work", home: true, dock: { fourth: "/nope", fifth: "auto" } })).toHaveLength(4);   // an unknown screen is left out
  });

  it("stays Links and Career when Home doesn't change with the time of day", () => {
    expect(labels({ phase: "morning", home: true }, false)).toEqual(["Home", "SirisAI", "Siris", "Links", "Career"]);
  });
});

describe("tab badges", () => {
  it("dots Siris when the brain has things waiting, and Smart home when the house needs you", () => {
    expect(dockBadges([], 0)).toEqual({});
    expect(dockBadges([], 3)).toEqual({ "/brain": "3 waiting in the brain" });
    const items = [
      { source: "intruder_check", app: "sirisai" }, { source: "home_assistant_call_service", app: "sirisai" },
      { source: "second-brain", app: "sirisai" }, { source: "server-updates", app: "sirisai" },
    ];
    expect(dockBadges(items, 0)).toEqual({ "/brain": "1 waiting in the brain", "/house": "2 things at home need you" });
  });
});
