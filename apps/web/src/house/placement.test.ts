import { describe, expect, it } from "vitest";
import { activity, guessRoom, markers, moved, roomAt, spots } from "./placement";
import { deviceType } from "./devices";
import { FLOORS } from "./layout";

describe("guessRoom", () => {
  it("puts a device in the room its name points to, longest hint first", () => {
    expect(guessRoom({ name: "Lounge Apple TV", kind: "client" })).toBe("lounge");
    expect(guessRoom({ name: "HomePod Mini - Spare Bedroom", kind: "client" })).toBe("bed2");
    expect(guessRoom({ name: "Plug - Master Bedroom (1)", kind: "client" })).toBe("main");
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
    const out = spots(nodes, { x: { room: "garage", hidden: true }, pc: { room: "main", x: 1, z: 2 } });
    expect(out.map((s) => s.id).sort()).toEqual(["gw", "pc", "tv"]);
    const tv = out.find((s) => s.id === "tv")!;
    expect(tv.room.id).toBe("lounge");
    expect(tv.y).toBeCloseTo(5.7 + 1.1);
    expect(tv.x).toBeGreaterThan(tv.room.x);
    expect(tv.x).toBeLessThan(tv.room.x + tv.room.w);
    const pc = out.find((s) => s.id === "pc")!;
    expect([pc.room.id, pc.floor, pc.x, pc.z]).toEqual(["main", "first", 1, 2]);
  });

  it("follows the gateway when it's moved", () => {
    const out = spots(nodes, { gw: { room: "garage" } });
    expect(out.find((s) => s.id === "x")!.room.id).toBe("garage");
  });
});

describe("the layout", () => {
  const room = (id: string) => FLOORS.flatMap((f) => f.rooms).find((r) => r.id === id)!;
  const stairs = (floor: string) => FLOORS.find((f) => f.id === floor)!.rooms.flatMap((r) => r.furniture ?? []).filter((f) => f.kind === "stairs");

  it("stacks three flights of stairs in a walled corridor along the right wall, mid-way back, and none on the roof", () => {
    for (const f of ["ground", "first", "second"]) expect(FLOORS.find((x) => x.id === f)!.rooms.find((r) => r.id.startsWith("stairs"))!.walled).toBe(true);
    const flights = ["ground", "first", "second"].map((f) => stairs(f));
    for (const f of flights) expect(f).toHaveLength(1);
    expect(new Set(flights.map(([s]) => `${s.x},${s.z}`)).size).toBe(1);
    expect(flights[0][0].x).toBe(0);
    expect(flights[0][0].z).toBeGreaterThan(3.5);
    expect(stairs("roof")).toHaveLength(0);
  });

  it("puts the main bedroom at the front over the office, the spare over the garage, and the lounge and balcony at the front", () => {
    expect(room("main").z).toBe(0);
    expect(room("bed2").z).toBe(room("garage").z);
    expect(room("balcony").z).toBe(0);
    expect(room("lounge").z).toBeLessThan(room("kitchen").z);
  });

  it("has no overlapping rooms on a floor", () => {
    for (const f of FLOORS) {
      for (const a of f.rooms) for (const b of f.rooms) {
        if (a === b) continue;
        const overlap = a.x < b.x + b.w - 0.01 && b.x < a.x + a.w - 0.01 && a.z < b.z + b.d - 0.01 && b.z < a.z + a.d - 0.01;
        expect(overlap, `${a.id} overlaps ${b.id}`).toBe(false);
      }
    }
  });
});

describe("deviceType", () => {
  it("knows the devices on Brad's network by name", () => {
    const t = (name: string, kind: "client" | "gateway" | "switch" | "access_point" = "client", model: string | null = null) => deviceType({ name, kind, model });
    expect(t("Cloud Gateway Ultra", "gateway")).toBe("gateway");
    expect(t("U6+ (Lounge)", "access_point")).toBe("ap");
    expect(t("USW-Lite-8-PoE", "switch")).toBe("switch");
    expect([t("iPhone - Brad"), t("iPad - Dom"), t("Apple Watch - Brad"), t("Macbook - Brad")]).toEqual(["phone", "tablet", "watch", "laptop"]);
    expect([t("Windows - Gaming PC"), t("Synology NAS"), t("Pi - Torrent"), t("Home Assistent"), t("Linux - Server")]).toEqual(["desktop", "server", "server", "server", "server"]);
    expect([t("PlayStation 5"), t("Apple TV"), t("TV - Lounge"), t("Frame - Kitchen")]).toEqual(["console", "streamer", "tv", "frame"]);
    expect([t("HomePod - Lounge (1)"), t("Echo Dot - Lounge"), t("HomePod Mini - Office")]).toEqual(["speaker", "speaker", "speaker"]);
    expect([t("Hub - Blink"), t("Hub - Philips Hue 1"), t("Hub - Zigbee")]).toEqual(["hub", "hub", "hub"]);
    expect([t("P100"), t("Plug - Master Bedroom (2)"), t("Light Strip - Desk"), t("AC - Lounge")]).toEqual(["plug", "plug", "light", "climate"]);
    expect([t("Vacuum - Maria"), t("Button - Garage Door"), t("Garage Door"), t("Fridge - Office")]).toEqual(["vacuum", "sensor", "sensor", "appliance"]);
    expect([t("Kitchen lights", "client", "light"), t("Mystery thing")]).toEqual(["light", "device"]);
  });
});

describe("markers", () => {
  const nodes = [
    { id: "gw", name: "Cloud Gateway Ultra", kind: "gateway" as const, model: null },
    { id: "p1", name: "iPhone - Brad", kind: "client" as const, model: null },
    { id: "p2", name: "iPhone - Dom", kind: "client" as const, model: null },
    { id: "pc", name: "Windows - Gaming PC", kind: "client" as const, model: null },
    { id: "tv", name: "TV - Lounge", kind: "client" as const, model: null },
  ];
  const at = (x: number, z: number) => ({ x, z });
  const placements = { gw: { room: "office", ...at(3, 1) }, p1: { room: "office", ...at(3.5, 1.5) }, p2: { room: "office", ...at(4, 2) }, pc: { room: "office", ...at(4.5, 3.5) }, tv: { room: "lounge", ...at(3.5, 1.5) } };

  it("groups devices within 2 m on the same floor, but keeps the gateway and the picked device apart", () => {
    const where = spots(nodes, placements);
    const m = markers(nodes, where);
    expect(m.map((x) => x.ids.join("+")).sort()).toEqual(["gw", "p1+p2+pc", "tv"]);
    const group = m.find((x) => x.ids.length === 3)!;
    expect(group.types[0]).toBe("phone");
    expect(group.x).toBeCloseTo(4);
    expect(markers(nodes, where, 2, ["pc"]).map((x) => x.ids.join("+")).sort()).toEqual(["gw", "p1+p2", "pc", "tv"]);
  });

  it("moves dragged devices together, into the room they're dropped in", () => {
    const where = spots(nodes, placements);
    const next = moved(where, ["p1", "p2"], -2.5, 6, placements);
    expect(next.p1).toEqual({ room: "entry", x: 1, z: 7.5 });
    expect(next.p2).toEqual({ room: "garage", x: 1.5, z: 8 });
    expect(next.pc).toBe(placements.pc);
    expect(moved(where, ["tv"], 9, -9, placements).tv).toEqual({ room: "balcony", x: 5.3, z: 0.1 });
  });

  it("finds the room at a point, or the nearest one", () => {
    expect(roomAt("ground", 3, 1).id).toBe("office");
    expect(roomAt("roof", 0.5, 1).id).toBe("terrace");
    expect(roomAt("second", 0.5, 4).id).toBe("lounge");
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
