import { api, json } from "./client";

export interface WatchedDevice {
  id: string;
  name: string;
  kind: "gateway" | "switch" | "access_point" | "client" | null;
  first_seen: string | null;
  last_seen: string | null;
  trusted: boolean;
  important: boolean;
  blocked: boolean;
  online: boolean;
  offline_minutes: number | null;
}

export interface NetWatch { watching: boolean; devices: WatchedDevice[] }

const N = "/api/v1/netwatch";
const id = (x: string) => encodeURIComponent(x);

export const netwatch = {
  get: () => api<NetWatch>(N),
  trust: (device: string) => api<NetWatch>(`${N}/${id(device)}/trust`, { method: "POST" }),
  important: (device: string, important: boolean) => api<NetWatch>(`${N}/${id(device)}/important`, json({ important })),
  block: (device: string, blocked: boolean) => api<NetWatch>(`${N}/${id(device)}/block`, json({ blocked })),
};
