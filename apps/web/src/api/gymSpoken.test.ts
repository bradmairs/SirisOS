import { describe, expect, it } from "vitest";
import { parseSpoken } from "./gym";

describe("parseSpoken (6.9)", () => {
  it.each([
    ["100 by 5", { weight: 100, reps: 5 }],
    ["Bench press 82.5 kilos for 8", { weight: 82.5, reps: 8, name: "bench press" }],
    ["eighty two point five by six RPE 8", { weight: 82.5, reps: 6, rpe: 8 }],
    ["five reps at sixty", { weight: 60, reps: 5 }],
    ["bodyweight 12", { weight: null, reps: 12 }],
    ["10 reps", { reps: 10 }],
    ["sixty x 8", { weight: 60, reps: 8 }],
    ["one hundred and two point five by three", { weight: 102.5, reps: 3 }],
  ])("%s", (said, want) => expect(parseSpoken(said)).toEqual(want));
  it("ignores what isn't a set", () => expect(parseSpoken("what's next")).toBeNull());
});
