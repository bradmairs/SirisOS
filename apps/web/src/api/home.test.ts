import { describe, expect, it } from "vitest";
import { arrange, move } from "./home";

describe("arrange", () => {
  it("puts saved ids in saved order and leaves new ones in place", () => {
    expect(arrange(["clock", "weather", "server", "health"], ["server", "clock"])).toEqual(["server", "weather", "clock", "health"]);
    expect(arrange(["a", "b"], [])).toEqual(["a", "b"]);
    expect(arrange(["a", "b"], ["gone", "b", "a"])).toEqual(["b", "a"]);
  });
});

describe("move", () => {
  it("swaps with a neighbour and stops at the ends", () => {
    expect(move(["a", "b", "c"], "b", -1)).toEqual(["b", "a", "c"]);
    expect(move(["a", "b", "c"], "c", 1)).toEqual(["a", "b", "c"]);
  });
});
