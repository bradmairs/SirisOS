import { api } from "./client";
import type { Placements } from "./house";
import { guessRoom } from "../house/placement";

export interface PowerSensor { entity_id: string; name: string; watts: number }

export interface Power {
  available: boolean;
  configured: boolean;
  house_watts: number | null;
  solar_watts: number | null;
  power: PowerSensor[];
  meters: { entity_id: string; name: string; kwh: number }[];
  today_kwh: number | null;
  method: string | null;
}

export const power = { get: () => api<Power>("/api/v1/power") };

export function watts(w: number | null | undefined): string {
  if (w == null) return "–";
  return w >= 1000 ? `${(w / 1000).toFixed(w >= 10_000 ? 0 : 1)} kW` : `${Math.round(w)} W`;
}

/** The room a sensor is in: where you put it, else by its name; null when its name says nothing. */
export function sensorRoom(s: PowerSensor, placements: Placements): string | null {
  const own = placements[s.entity_id];
  if (own) return own.hidden ? null : own.room;
  const guess = guessRoom({ name: s.name, kind: "client" }, "");
  return guess || null;
}

/** Watts per room, for the house's glow. */
export function roomWatts(p: Power | null | undefined, placements: Placements): Record<string, number> {
  const out: Record<string, number> = {};
  for (const s of p?.power ?? []) {
    const room = sensorRoom(s, placements);
    if (room && s.watts > 0) out[room] = (out[room] ?? 0) + s.watts;
  }
  return out;
}

/** 2 kW and over glows fully; the colour is the house's "power" green. */
export function powerGlow(rooms: Record<string, number>): Record<string, { color: number; strength: number }> {
  return Object.fromEntries(Object.entries(rooms).map(([room, w]) => [room, { color: 0x6fe39a, strength: Math.min(1, 0.25 + w / 2000) }]));
}
