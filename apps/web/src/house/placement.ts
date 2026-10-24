import type { NetNode, Placements } from "../api/house";
import { ROOMS, floorOf, type Room } from "./layout";

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

export interface Spot { id: string; room: Room; x: number; y: number; z: number }

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
    const level = floorOf((room as Room & { floor: Parameters<typeof floorOf>[0] }).floor).level;
    const cols = Math.ceil(Math.sqrt(ids.length * (room.w / room.d)));
    const rows = Math.ceil(ids.length / cols);
    ids.forEach((id, i) => {
      const own = placements[id];
      const c = i % cols, r = Math.floor(i / cols);
      const x = own?.x ?? room.x + ((c + 0.5) / cols) * room.w;
      const z = own?.z ?? room.z + ((r + 0.5) / rows) * room.d;
      out.push({ id, room: roomOf.get(id)!, x, y: level + 1.1, z });
    });
  }
  return out;
}

/** How lively a link looks for a rate: 0 (idle) to 1 (100 Mb/s or more), on a log scale. */
export function activity(bps: number): number {
  if (bps <= 0) return 0;
  return Math.max(0, Math.min(1, Math.log10(bps * 8) / 8));
}
