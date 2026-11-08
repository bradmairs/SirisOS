import { describe, expect, it } from "vitest";
import { dockBadges, dockItems } from "./Dock";

// A fixed time of day away from gym time, so these don't depend on when they run.
const NOON = new Date(2026, 10, 5, 12);
const at = (h: number, m = 0) => new Date(2026, 10, 5, h, m);
const labels = (ctx: Parameters<typeof dockItems>[0], adapt = true, when = NOON) => dockItems(ctx, adapt, when).map((n) => n.label);

describe("the tab bar", () => {
  it("keeps Home, SirisAI and Siris first, always", () => {
    for (const phase of ["morning", "work", "weekend", "evening", "winddown", "night"] as const) {
      expect(labels({ phase, home: true }).slice(0, 3)).toEqual(["Home", "SirisAI", "Siris"]);
    }
  });

  it("makes the fourth the brief in the morning, Wrap Up from wind down, Links otherwise", () => {
    expect(labels({ phase: "morning", home: true })[3]).toBe("Brief");
    expect(labels({ phase: "winddown", home: true })[3]).toBe("Wrap Up");
    expect(labels({ phase: "night", home: true })[3]).toBe("Wrap Up");
    expect(labels({ phase: "work", home: true })[3]).toBe("Links");
    expect(labels({ phase: "evening", home: true })[3]).toBe("Links");
  });

  it("makes the fifth Work at work (7.2), Smart Home at home, Tasks out, Career when it can't tell", () => {
    expect(labels({ phase: "work", home: true })[4]).toBe("Work");     // even working from home
    expect(labels({ phase: "evening", home: true })[4]).toBe("Smart Home");
    expect(labels({ phase: "weekend", home: false })[4]).toBe("Tasks");
    expect(labels({ phase: "evening", home: null })[4]).toBe("Career");
  });

  it("uses what you picked in Times of day over the automatic choice", () => {
    expect(labels({ phase: "evening", home: true, dock: { fourth: "/review", fifth: "auto" } })).toEqual(["Home", "SirisAI", "Siris", "Review", "Smart Home"]);
    expect(labels({ phase: "work", home: true, dock: { fourth: "auto", fifth: "/engineering" } })[4]).toBe("Engineering");
    expect(labels({ phase: "work", home: true, dock: { fourth: "/nope", fifth: "auto" } })).toHaveLength(4);   // an unknown screen is left out
  });

  it("stays Links and Career when Home doesn't change with the time of day", () => {
    expect(labels({ phase: "morning", home: true }, false)).toEqual(["Home", "SirisAI", "Siris", "Links", "Career"]);
  });
});

describe("gym time on the tab bar", () => {
  const morning = { phase: "morning" as const, home: true };
  const gym = () => dockItems(morning, true, at(7)).find((n) => n.to === "/gym")!;

  it("shows SirisGym from 6 to 8 am, in the fifth place, then not", () => {
    expect(dockItems(morning, true, at(5, 59)).some((n) => n.to === "/gym")).toBe(false);
    expect(dockItems(morning, true, at(6)).map((n) => n.to)).toEqual(["/", "/assistant", "/brain", "/brief", "/gym"]);
    expect(dockItems(morning, true, at(7, 59)).at(-1)!.to).toBe("/gym");
    expect(dockItems(morning, true, at(8)).at(-1)!.to).toBe("/house");
    expect(gym().label).toBe("SirisGym");
  });

  it("goes in the fourth place if you've picked the fifth, and leaves both picks alone", () => {
    const pick = (fourth: string, fifth: string) => dockItems({ ...morning, dock: { fourth, fifth } }, true, at(7)).slice(3).map((n) => n.to);
    expect(pick("auto", "/career")).toEqual(["/gym", "/career"]);
    expect(pick("/links", "/career")).toEqual(["/links", "/career"]);
    expect(pick("/gym", "auto")).toEqual(["/gym", "/house"]);   // not twice
  });

  it("stays away when Home doesn't change with the time of day", () => {
    expect(labels(morning, false, at(7))).toEqual(["Home", "SirisAI", "Siris", "Links", "Career"]);
  });
});

describe("tab badges", () => {
  it("dots Siris when the brain has things waiting, and Smart Home when the house needs you", () => {
    expect(dockBadges([], 0)).toEqual({});
    expect(dockBadges([], 3)).toEqual({ "/brain": "3 waiting in the brain" });
    const items = [
      { source: "intruder_check", app: "sirisai" }, { source: "home_assistant_call_service", app: "sirisai" },
      { source: "second-brain", app: "sirisai" }, { source: "server-updates", app: "sirisai" },
    ];
    expect(dockBadges(items, 0)).toEqual({ "/brain": "1 waiting in the brain", "/house": "2 things at home need you" });
  });
});
