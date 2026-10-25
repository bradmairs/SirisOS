import { describe, expect, it } from "vitest";
import { dockItems } from "./Dock";

const labels = (ctx: Parameters<typeof dockItems>[0], adapt = true) => dockItems(ctx, adapt).map((n) => n.label);

describe("the tab bar", () => {
  it("swaps Career for Smart home when you're home outside work hours", () => {
    expect(labels({ phase: "evening", home: true })).toEqual(["Home", "SirisAI", "Siris", "Links", "Smart home"]);
    expect(labels({ phase: "weekend", home: true }).at(-1)).toBe("Smart home");
  });

  it("keeps Career at work, even working from home, and when you're out or it can't tell", () => {
    expect(labels({ phase: "work", home: true }).at(-1)).toBe("Career");
    expect(labels({ phase: "evening", home: false }).at(-1)).toBe("Career");
    expect(labels({ phase: "evening", home: null }).at(-1)).toBe("Career");
  });

  it("stays put when Home doesn't change with the time of day", () => {
    expect(labels({ phase: "evening", home: true }, false).at(-1)).toBe("Career");
  });
});
