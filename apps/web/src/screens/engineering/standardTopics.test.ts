import { describe, expect, it } from "vitest";
import type { StandardHit } from "../../api/engineering";
import { byTopic } from "./Standards";

const hit = (title: string, category?: string) => ({ document: { title, category } } as unknown as StandardHit);

describe("11.20: standards by topic", () => {
  it("groups A to Z with Other last, and orders books by number", () => {
    const groups = byTopic([hit("ARR Book 10", "Hydrology"), hit("ARR Book 2", "Hydrology"), hit("AS/NZS 3500.3"), hit("ADWG", "Drinking water")]);
    expect(groups.map(([t]) => t)).toEqual(["Drinking water", "Hydrology", "Other"]);
    expect(groups[1][1].map((h) => h.document.title)).toEqual(["ARR Book 2", "ARR Book 10"]);
  });
});
