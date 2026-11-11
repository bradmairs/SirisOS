import { api } from "./client";

export type LabKind = "internet" | "modem" | "gateway" | "switch" | "access_point" | "server" | "nas" | "ups" | "docker" | "device" | "other";
export interface LabNode {
  id: string; label: string; kind: LabKind; parent: string | null; parent_guessed?: boolean;
  online: boolean | null; found: "built in" | "network" | "terminal" | "sirisai" | "you";
  detail?: string | null; model?: string; notes?: string;
}
export interface HomeLab { nodes: LabNode[]; clients: { total: number; online: number }; sources: { network: boolean; servers: boolean; docker: boolean } }

const H = "/api/v1/homelab";
export const homelab = {
  get: () => api<HomeLab>(H),
  change: (id: string, c: Partial<Pick<LabNode, "label" | "model" | "notes" | "parent" | "kind">>) =>
    api<HomeLab>(`${H}/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(c) }),
  add: (label: string, kind: LabKind, parent?: string) => api<HomeLab>(H, { method: "POST", body: JSON.stringify({ label, kind, parent: parent ?? null }) }),
  remove: (id: string) => api<HomeLab>(`${H}/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

export const KIND_LABEL: Record<LabKind, string> = {
  internet: "Internet", modem: "Modem", gateway: "Gateway", switch: "Switch", access_point: "Access point", server: "Server",
  nas: "NAS", ups: "UPS", docker: "Docker", device: "Device", other: "Other",
};

export interface Placed extends LabNode { x: number; y: number; depth: number }

/** A top-down tree: each box sits over the middle of what plugs into it, leaves side by side. */
export function layout(nodes: LabNode[], w = 168, h = 64, gapX = 20, gapY = 64): { placed: Placed[]; width: number; height: number } {
  const kids = new Map<string | null, LabNode[]>();
  for (const n of nodes) kids.set(n.parent, [...(kids.get(n.parent) ?? []), n]);
  for (const list of kids.values()) list.sort((a, b) => order(a) - order(b) || a.label.localeCompare(b.label));
  const placed: Placed[] = [];
  let next = 0;
  let deepest = 0;
  const walk = (n: LabNode, depth: number, seen: Set<string>): number => {
    deepest = Math.max(deepest, depth);
    const children = (kids.get(n.id) ?? []).filter((c) => !seen.has(c.id));
    let x: number;
    if (!children.length) { x = next * (w + gapX); next += 1; }
    else {
      const xs = children.map((c) => walk(c, depth + 1, new Set([...seen, c.id])));
      x = (xs[0] + xs[xs.length - 1]) / 2;
    }
    placed.push({ ...n, x, y: depth * (h + gapY), depth });
    return x;
  };
  for (const root of kids.get(null) ?? []) walk(root, 0, new Set([root.id]));
  placed.sort((a, b) => a.depth - b.depth || a.x - b.x);  // top-down, left to right (for reading out)
  return { placed, width: Math.max(1, next) * (w + gapX) - gapX, height: (deepest + 1) * (h + gapY) - gapY };
}

const RANK: LabKind[] = ["modem", "gateway", "switch", "access_point", "server", "nas", "docker", "ups", "device", "other"];
const order = (n: LabNode) => { const i = RANK.indexOf(n.kind); return i < 0 ? 99 : i; };
