/**
 * 13 Peck Walk, Alphington: a four-level townhouse, laid out from Brad's
 * walk-through videos (October 2026). Metres. x runs across the house (0 is
 * the side the stairs climb), z runs from the street (0) to the back.
 * The proportions are a best reading of the videos, not a survey: change a
 * number here and the model follows.
 */

export type FloorId = "ground" | "first" | "second" | "roof";

export interface Box { x: number; z: number; w: number; d: number }

export interface Furniture extends Box {
  kind: "bed" | "desk" | "car" | "sofa" | "table" | "island" | "bench" | "tv" | "bbq" | "plant" | "robe" | "shower" | "toilet" | "vanity" | "cabinet" | "chair" | "pergola" | "stairs" | "door";
  h: number;
  label?: string;
}

export interface Room extends Box {
  id: string;
  name: string;
  outdoor?: boolean;
  /** Words that put a device here when it isn't placed by hand (e.g. "tv" -> Lounge). */
  hints?: string[];
  furniture?: Furniture[];
}

export interface Floor {
  id: FloorId;
  name: string;
  /** Floor level above the ground slab. */
  level: number;
  /** Ceiling height (the roof's is its parapet). */
  height: number;
  rooms: Room[];
}

export const HOUSE = { width: 5.4, depth: 13, address: "13 Peck Walk, Alphington" };

const STAIRS: Furniture = { kind: "stairs", x: 0, z: 2.2, w: 1.05, d: 3.8, h: 0.2, label: "Stairs" };

export const FLOORS: Floor[] = [
  {
    id: "ground", name: "Ground", level: 0, height: 2.7, rooms: [
      { id: "garden", name: "Front garden", outdoor: true, x: 0, z: -2.6, w: 5.4, d: 2.6, hints: ["doorbell", "front", "gate", "garden"],
        furniture: [{ kind: "plant", x: 0.3, z: -2.2, w: 0.8, d: 0.8, h: 0.7 }, { kind: "plant", x: 4.2, z: -2.3, w: 0.9, d: 0.9, h: 0.9 },
          { kind: "door", x: 2.0, z: -2.65, w: 1.0, d: 0.08, h: 1.2, label: "Gate" }] },
      { id: "entry", name: "Entry & stairs", x: 0, z: 0, w: 2.1, d: 7, hints: ["entry", "hall", "door lock", "front door"],
        furniture: [{ kind: "door", x: 1.0, z: -0.05, w: 0.9, d: 0.08, h: 2.1, label: "Front door" }, STAIRS] },
      { id: "office", name: "Office", x: 2.1, z: 0, w: 3.3, d: 4.4, hints: ["office", "pc", "desktop", "gaming", "playstation", "ps5", "printer", "monitor", "mac"],
        furniture: [{ kind: "desk", x: 3.0, z: 3.2, w: 2.2, d: 0.75, h: 0.75, label: "Desk" }, { kind: "chair", x: 3.6, z: 2.5, w: 0.6, d: 0.6, h: 1.1 },
          { kind: "cabinet", x: 2.2, z: 0.2, w: 0.45, d: 0.4, h: 1.8, label: "Display cabinet" }] },
      { id: "store", name: "Store & laundry", x: 2.1, z: 4.4, w: 3.3, d: 2.6, hints: ["laundry", "washer", "dryer", "store"] },
      { id: "garage", name: "Garage", x: 0, z: 7, w: 5.4, d: 6, hints: ["garage", "car", "charger", "freezer", "nas", "synology", "server"],
        furniture: [{ kind: "car", x: 1.4, z: 7.6, w: 1.9, d: 4.7, h: 1.5, label: "Car" }, { kind: "cabinet", x: 4.3, z: 8.0, w: 0.9, d: 2.2, h: 1.8, label: "Storage" },
          { kind: "door", x: 0.4, z: 12.95, w: 4.6, d: 0.1, h: 2.2, label: "Garage door" }] },
    ],
  },
  {
    id: "first", name: "First", level: 2.9, height: 2.6, rooms: [
      { id: "stairs1", name: "Stairs", x: 0, z: 0, w: 1.05, d: 6.4, furniture: [STAIRS] },
      { id: "bed2", name: "Front bedroom", x: 1.05, z: 0, w: 4.35, d: 4.2, hints: ["bedroom 2", "guest", "front bedroom", "spare"],
        furniture: [{ kind: "bed", x: 2.4, z: 1.5, w: 1.6, d: 2.0, h: 0.55, label: "Bed" }, { kind: "robe", x: 1.15, z: 0.4, w: 0.6, d: 2.4, h: 2.2, label: "Robe" }] },
      { id: "bath", name: "Bathroom", x: 2.1, z: 4.2, w: 3.3, d: 3.0, hints: ["bathroom", "bath", "toothbrush", "scale"],
        furniture: [{ kind: "shower", x: 4.2, z: 4.3, w: 1.1, d: 1.1, h: 2.0, label: "Shower" }, { kind: "toilet", x: 2.3, z: 6.4, w: 0.45, d: 0.7, h: 0.45 },
          { kind: "vanity", x: 3.0, z: 6.6, w: 1.1, d: 0.5, h: 0.85, label: "Vanity" }] },
      { id: "hall1", name: "Hallway", x: 0, z: 6.4, w: 2.1, d: 3.2 },
      { id: "main", name: "Main bedroom", x: 0, z: 9.6, w: 5.4, d: 3.4, hints: ["main bedroom", "master", "brad", "bedroom", "bedside"],
        furniture: [{ kind: "bed", x: 1.8, z: 10.9, w: 1.8, d: 2.0, h: 0.6, label: "Bed" }, { kind: "robe", x: 0.1, z: 9.8, w: 0.6, d: 2.0, h: 2.2, label: "Robe" }] },
    ],
  },
  {
    id: "second", name: "Second", level: 5.7, height: 2.8, rooms: [
      { id: "stairs2", name: "Stairs", x: 0, z: 0, w: 1.05, d: 6.4, furniture: [STAIRS] },
      { id: "kitchen", name: "Kitchen", x: 1.05, z: 0, w: 4.35, d: 4.4, hints: ["kitchen", "fridge", "oven", "dishwasher", "cooktop", "rangehood", "nest hub", "echo"],
        furniture: [{ kind: "bench", x: 1.2, z: 0.1, w: 4.1, d: 0.65, h: 0.9, label: "Cooktop & bench" }, { kind: "island", x: 2.2, z: 2.2, w: 2.4, d: 0.95, h: 0.9, label: "Island" }] },
      { id: "dining", name: "Dining", x: 1.05, z: 4.4, w: 4.35, d: 2.6, hints: ["dining"],
        furniture: [{ kind: "table", x: 2.4, z: 5.0, w: 1.6, d: 0.9, h: 0.75, label: "Table" }] },
      { id: "lounge", name: "Lounge", x: 0, z: 7, w: 5.4, d: 4.2, hints: ["lounge", "living", "tv", "apple tv", "chromecast", "sonos", "soundbar", "speaker", "xbox"],
        furniture: [{ kind: "sofa", x: 0.3, z: 8.0, w: 0.95, d: 2.4, h: 0.85, label: "Sofa" }, { kind: "tv", x: 5.25, z: 8.2, w: 0.08, d: 1.6, h: 0.95, label: "TV" },
          { kind: "cabinet", x: 4.9, z: 7.9, w: 0.45, d: 2.2, h: 0.45 }] },
      { id: "balcony", name: "Balcony", outdoor: true, x: 0, z: 11.2, w: 5.4, d: 1.8, hints: ["balcony"],
        furniture: [{ kind: "chair", x: 0.6, z: 11.6, w: 0.7, d: 0.7, h: 0.8 }, { kind: "chair", x: 1.5, z: 11.6, w: 0.7, d: 0.7, h: 0.8 },
          { kind: "table", x: 2.6, z: 11.6, w: 1.1, d: 0.6, h: 0.4 }, { kind: "plant", x: 4.6, z: 11.5, w: 0.6, d: 0.6, h: 1.1 }] },
    ],
  },
  {
    id: "roof", name: "Roof", level: 8.7, height: 1.1, rooms: [
      { id: "stairpod", name: "Stair housing", x: 0, z: 2.2, w: 1.6, d: 3.8, furniture: [STAIRS, { kind: "door", x: 1.6, z: 5.2, w: 0.08, d: 0.85, h: 2.1, label: "Door" }] },
      { id: "terrace", name: "Terrace", outdoor: true, x: 1.6, z: 0, w: 3.8, d: 7, hints: ["terrace", "roof", "festoon", "outdoor"],
        furniture: [{ kind: "plant", x: 4.6, z: 0.3, w: 0.6, d: 0.6, h: 0.8 }, { kind: "table", x: 2.4, z: 2.4, w: 1.8, d: 0.9, h: 0.75, label: "Table" }] },
      { id: "bbq", name: "BBQ area", outdoor: true, x: 0, z: 7, w: 5.4, d: 6, hints: ["bbq", "grill", "weber"],
        furniture: [{ kind: "pergola", x: 1.4, z: 7.4, w: 3.6, d: 3.4, h: 2.4, label: "Pergola" }, { kind: "bbq", x: 0.4, z: 11.2, w: 1.3, d: 0.65, h: 1.0, label: "BBQ" },
          { kind: "plant", x: 4.6, z: 12.2, w: 0.6, d: 0.6, h: 1.0 }] },
    ],
  },
];

export const ROOMS: (Room & { floor: FloorId })[] = FLOORS.flatMap((f) => f.rooms.map((r) => ({ ...r, floor: f.id })));

export function roomById(id: string) {
  return ROOMS.find((r) => r.id === id);
}

export function floorOf(id: FloorId) {
  return FLOORS.find((f) => f.id === id)!;
}
