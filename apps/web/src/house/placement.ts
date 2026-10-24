import type { NetNode, Placements } from "../api/house";
import { FLOORS, HOUSE, ROOMS, floorOf, type FloorId, type Room } from "./layout";
import { deviceType, type DeviceType } from "./devices";

/** Where a device goes when it hasn't been placed by hand: a room whose hints
 * match its name, else the gateway's room (the office, where the rack is). */
export function guessRoom(node: Pick<NetNode, "name" | "kind">, gatewayRoom = "office"): string {
  if (node.kind === "gateway") return gatewayRoom;
  const name = node.name.toLowerCase();
  let best: { id: string; len: number } | null = null;
  for (const r of ROOMS) {
    for (const h of r.hints ?? []) {
      if (name.includes(h) && (!best || h.length > best.len)) best = { id: r.id, len: h.length };
    }
  }
  return best?.id ?? gatewayRoom;
}

export interface Spot { id: string; room: Room; floor: FloorId; x: number; y: number; z: number }

/** A position for every device: its own spot if it has one, else spread on a
 * grid inside its room, at about desk height. */
export function spots(nodes: Pick<NetNode, "id" | "name" | "kind">[], placements: Placements): Spot[] {
  const gatewayRoom = placements[nodes.find((n) => n.kind === "gateway")?.id ?? ""]?.room ?? "office";
  const byRoom = new Map<string, string[]>();
  const roomOf = new Map<string, Room>();
  for (const n of nodes) {
    if (placements[n.id]?.hidden) continue;
    const id = placements[n.id]?.room ?? guessRoom(n, gatewayRoom);
    const room = ROOMS.find((r) => r.id === id) ?? ROOMS.find((r) => r.id === "office")!;
    roomOf.set(n.id, room);
    byRoom.set(room.id, [...(byRoom.get(room.id) ?? []), n.id]);
  }
  const out: Spot[] = [];
  for (const [roomId, ids] of byRoom) {
    const room = ROOMS.find((r) => r.id === roomId)!;
    const floor = (room as Room & { floor: FloorId }).floor;
    const level = floorOf(floor).level;
    const cols = Math.ceil(Math.sqrt(ids.length * (room.w / room.d)));
    const rows = Math.ceil(ids.length / cols);
    ids.forEach((id, i) => {
      const own = placements[id];
      const c = i % cols, r = Math.floor(i / cols);
      const x = own?.x ?? room.x + ((c + 0.5) / cols) * room.w;
      const z = own?.z ?? room.z + ((r + 0.5) / rows) * room.d;
      out.push({ id, room: roomOf.get(id)!, floor, x, y: level + 1.1, z });
    });
  }
  return out;
}

/** The room on a floor at a point, or the nearest one when the point is between rooms
 * (or on the stairs, which aren't a room you put things in). */
export function roomAt(floor: FloorId, x: number, z: number): Room {
  const rooms = FLOORS.find((f) => f.id === floor)!.rooms.filter((r) => !r.id.startsWith("stairs"));
  const gap = (r: Room) => Math.hypot(Math.max(r.x - x, 0, x - r.x - r.w), Math.max(r.z - z, 0, z - r.z - r.d));
  return rooms.reduce((best, r) => (gap(r) < gap(best) ? r : best));
}

/** New placements after dragging devices by (dx, dz) on their floor: each keeps
 * its place relative to the others, and lands in the room it's dropped in. */
export function moved(where: Spot[], ids: string[], dx: number, dz: number, placements: Placements): Placements {
  const next: Placements = { ...placements };
  for (const s of where) {
    if (!ids.includes(s.id)) continue;
    const x = clamp(s.x + dx, 0.1, HOUSE.width - 0.1);
    const z = clamp(s.z + dz, s.floor === "ground" ? -2.5 : 0.1, HOUSE.depth - 0.1);
    next[s.id] = { room: roomAt(s.floor, x, z).id, x: round(x), z: round(z) };
  }
  return next;
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const round = (v: number) => Math.round(v * 100) / 100;

/** One thing drawn in the house: a device, or several close together. */
export interface Marker {
  /** Stable while the same devices are in it. */
  key: string;
  ids: string[];
  /** The members' looks, most common first. */
  types: DeviceType[];
  floor: FloorId;
  x: number;
  y: number;
  z: number;
}

/** Devices within `radius` metres of each other on a floor become one marker, so
 * the house isn't a cloud of dots. The gateway, switches and access points stay
 * on their own (the links run from them), and so does anything in `apart` (the
 * device being looked at or moved). */
export function markers(nodes: Pick<NetNode, "id" | "name" | "kind" | "model">[], where: Spot[], radius = 2, apart: string[] = []): Marker[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const solo = (s: Spot) => byId.get(s.id)?.kind !== "client" || apart.includes(s.id);
  const near = (a: Spot, b: Spot) => a.floor === b.floor && Math.hypot(a.x - b.x, a.z - b.z) <= radius;
  const out: Marker[] = [];
  let left = where.filter((s) => byId.has(s.id));
  for (const s of left.filter(solo)) out.push(marker([s], byId));
  left = left.filter((s) => !solo(s)).sort((a, b) => (a.id < b.id ? -1 : 1));
  // Greedy: the device with the most neighbours seeds a group of everything near it.
  while (left.length) {
    let seed = left[0], most = -1;
    for (const s of left) {
      const n = left.filter((o) => near(s, o)).length;
      if (n > most) { seed = s; most = n; }
    }
    const group = left.filter((o) => near(seed, o));
    out.push(marker(group, byId));
    left = left.filter((o) => !group.includes(o));
  }
  return out;
}

function marker(group: Spot[], byId: Map<string, Pick<NetNode, "name" | "kind" | "model">>): Marker {
  const counts = new Map<DeviceType, number>();
  for (const s of group) {
    const t = deviceType(byId.get(s.id)!);
    counts.set(t, (counts.get(t) ?? 0) + 1);
  }
  const ids = group.map((s) => s.id).sort();
  return {
    key: ids.join("|"),
    ids,
    types: [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([t]) => t),
    floor: group[0].floor,
    x: group.reduce((t, s) => t + s.x, 0) / group.length,
    y: group[0].y,
    z: group.reduce((t, s) => t + s.z, 0) / group.length,
  };
}

/** How lively a link looks for a rate: 0 (idle) to 1 (100 Mb/s or more), on a log scale. */
export function activity(bps: number): number {
  if (bps <= 0) return 0;
  return Math.max(0, Math.min(1, Math.log10(bps * 8) / 8));
}
