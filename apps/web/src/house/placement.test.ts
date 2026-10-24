import { describe, expect, it } from "vitest";
import { activity, guessRoom, spots } from "./placement";

describe("guessRoom", () => {
  it("puts a device in the room its name points to, longest hint first", () => {
    expect(guessRoom({ name: "Lounge Apple TV", kind: "client" })).toBe("lounge");
    expect(guessRoom({ name: "Front bedroom AC", kind: "client" })).toBe("bed2");
    expect(guessRoom({ name: "Weber grill", kind: "client" })).toBe("bbq");
    expect(guessRoom({ name: "Mystery thing", kind: "client" })).toBe("office");
    expect(guessRoom({ name: "Lounge", kind: "gateway" }, "garage")).toBe("garage");
  });
});

describe("spots", () => {
  const nodes = [
    { id: "gw", name: "UCG Ultra", kind: "gateway" as const },
    { id: "tv", name: "Lounge TV", kind: "client" as const },
    { id: "pc", name: "Gaming PC", kind: "client" as const },
    { id: "x", name: "Old phone", kind: "client" as const },
  ];

  it("spreads devices inside their rooms at desk height, honouring placements", () => {
    const out = spots(nodes, { x: { room: "garage", hidden: true }, pc: { room: "main", x: 1, z: 10 } });
    expect(out.map((s) => s.id).sort()).toEqual(["gw", "pc", "tv"]);
    const tv = out.find((s) => s.id === "tv")!;
    expect(tv.room.id).toBe("lounge");
    expect(tv.y).toBeCloseTo(5.7 + 1.1);
    expect(tv.x).toBeGreaterThan(tv.room.x);
    expect(tv.x).toBeLessThan(tv.room.x + tv.room.w);
    const pc = out.find((s) => s.id === "pc")!;
    expect([pc.room.id, pc.x, pc.z]).toEqual(["main", 1, 10]);
  });

  it("follows the gateway when it's moved", () => {
    const out = spots(nodes, { gw: { room: "garage" } });
    expect(out.find((s) => s.id === "x")!.room.id).toBe("garage");
  });
});

describe("activity", () => {
  it("is 0 when idle and 1 at 100 Mb/s or more", () => {
    expect(activity(0)).toBe(0);
    expect(activity(12.5e6)).toBe(1);
    expect(activity(1e9)).toBe(1);
    expect(activity(1250)).toBeGreaterThan(0.4);
  });
});
