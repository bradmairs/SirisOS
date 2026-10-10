/** Parity with the server-side port (apps/backend/app/engineering/calculators.py,
 * ADR 110): SirisAI runs the calculators through the API, so a spoken answer
 * must match this screen. calculator-cases.json holds inputs and these
 * results; the backend suite runs the same cases through Python.
 *
 *   WRITE_CALC_CASES=1 npm test -- calculators.parity   (after changing a formula)
 */
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { CALCULATORS, InputError } from "./calculators";

// vitest runs from apps/web (jsdom gives import.meta.url an http scheme).
const FILE = resolve(process.cwd(), "src/engineering/calculator-cases.json");

interface Case {
  calculator: string;
  inputs: Record<string, number>;
  results?: { label: string; value: string }[];
  error?: string;
}

const SCALES = [1, 1.37, 0.61];
// Inputs that must fail the same way on both sides.
const BAD: Case[] = [
  { calculator: "partFullPipe", inputs: { d: 0.3, y: 0.45, n: 0.013, s: 0.005 } },
  { calculator: "rationalMethod", inputs: { c: 1.4, i: 100, a: 1 } },
  { calculator: "fullPipe", inputs: { d: 0, n: 0.013, s: 0.005 } },
  { calculator: "buoyancy", inputs: { od: 0.45, id: 0.55, l: 1, pd: 2400, c: 0.75, g: 10 } },
  { calculator: "pumpPower", inputs: { q: 0.05, h: 20, e: 120 } },
];

function compute(c: Case): Case {
  const calculator = CALCULATORS.find((x) => x.id === c.calculator)!;
  try {
    return { ...c, results: calculator.compute(c.inputs) };
  } catch (error) {
    if (error instanceof InputError) return { ...c, error: error.message };
    throw error;
  }
}

function cases(): Case[] {
  const good = CALCULATORS.flatMap((calculator) =>
    SCALES.map((scale) => ({
      calculator: calculator.id,
      // Scale everything except dimensionless coefficients that must stay in range.
      inputs: Object.fromEntries(
        calculator.fields.map((f) => [f.key, ["c", "cd", "e", "n"].includes(f.key) && calculator.id !== "darcyWeisbach" && calculator.id !== "hazenWilliams" ? Number(f.initial) : Number((Number(f.initial) * scale).toPrecision(6))]),
      ),
    })),
  );
  return [...good, ...BAD].map(compute);
}

describe("calculator parity cases", () => {
  it("calculator-cases.json matches what the screen computes", () => {
    const now = cases();
    if (process.env.WRITE_CALC_CASES === "1") writeFileSync(FILE, JSON.stringify(now, null, 2) + "\n");
    const saved = JSON.parse(readFileSync(FILE, "utf8")) as Case[];
    expect(saved).toEqual(now);
    expect(saved.filter((c) => c.error)).toHaveLength(BAD.length);
  });
});
