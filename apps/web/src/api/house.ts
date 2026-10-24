import { api } from "./client";

export interface NetNode {
  id: string;
  name: string;
  kind: "gateway" | "switch" | "access_point" | "client";
  model: string | null;
  wired: boolean | null;
  online: boolean;
  /** The switch or access point it connects through; null is the gateway. */
  uplink: string | null;
  rx_bps: number;
  tx_bps: number;
}

export interface Network {
  configured: boolean;
  guest_mode: boolean;
  checked_at: string;
  wan: { rx_bps?: number; tx_bps?: number; isp?: string | null } | null;
  nodes: NetNode[];
}

/** Where each device sits: a room, and optionally a spot in it (metres). */
export type Placements = Record<string, { room: string; x?: number; z?: number; hidden?: boolean }>;

export const house = {
  network: () => api<Network>("/api/v1/assistant/network"),
  placements: () => api<{ placements: Placements }>("/api/v1/house/placements"),
  place: (placements: Placements) => api<{ placements: Placements }>("/api/v1/house/placements", { method: "PUT", body: JSON.stringify({ placements }) }),
};

export function rate(bps: number): string {
  const bits = bps * 8;
  if (bits >= 1e6) return `${(bits / 1e6).toFixed(bits >= 1e7 ? 0 : 1)} Mb/s`;
  if (bits >= 1e3) return `${Math.round(bits / 1e3)} kb/s`;
  return bits > 0 ? `${Math.round(bits)} b/s` : "idle";
}
