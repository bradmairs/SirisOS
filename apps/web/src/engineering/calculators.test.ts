import { describe, expect, it } from "vitest";
import { CALCULATORS, CALCULATOR_BY_ID, InputError, calc, fieldLabel, run } from "./calculators";

// Same reference values as the Flutter engineering_calculators_test.dart.
const close = (actual: number, expected: number, tol: number) => expect(Math.abs(actual - expected)).toBeLessThanOrEqual(tol);

describe("calculators", () => {
  it("full circular Manning", () => {
    const r = calc.fullCircularPipe(0.45, 0.013, 0.005);
    close(r.flowM3s, 0.2016, 0.0001);
    close(r.velocityMs, 1.2676, 0.001);
  });
  it("part-full circular Manning at half depth", () => {
    const r = calc.partFullCircularPipe(0.6, 0.3, 0.013, 0.005);
    close(r.areaM2, 0.14137, 0.0001);
    close(r.flowM3s, 0.21709, 0.0001);
    close(r.velocityMs, 1.5356, 0.001);
  });
  it("minimum grade inverts Manning", () => {
    const r = calc.minimumCircularPipeGrade(0.45, 0.013, 0.2);
    close(r.slope, 0.004921, 0.000001);
    close(r.gradePercent, 0.4921, 0.0001);
  });
  it("rectangular channel", () => {
    const r = calc.rectangularChannel(1, 0.3, 0.015, 0.005);
    close(r.flowM3s, 0.46329, 0.0001);
    close(r.velocityMs, 1.5443, 0.001);
  });
  it("rectangular critical depth", () => {
    const r = calc.rectangularCriticalDepth(0.5, 1);
    close(r.depthM, 0.29431, 0.0001);
    close(r.velocityMs, 1.6989, 0.001);
  });
  it("rational method", () => close(calc.rationalMethod(0.8, 100, 1).flowM3s, 0.22222, 0.0001));
  it("weir", () => close(calc.rectangularWeir(0.62, 1, 0.3).flowM3s, 0.30079, 0.0001));
  it("orifice", () => {
    const r = calc.circularOrifice(0.62, 0.15, 1);
    close(r.flowM3s, 0.04852, 0.0001);
    close(r.velocityMs, 2.7458, 0.001);
  });
  it("Hazen-Williams", () => {
    const r = calc.hazenWilliams(0.05, 0.2, 100, 140);
    close(r.headlossM, 1.1169, 0.001);
    close(r.velocityMs, 1.5915, 0.001);
  });
  it("Darcy-Weisbach", () => {
    const r = calc.darcyWeisbach(0.05, 0.2, 100, 0.045);
    close(r.reynoldsNumber, 317042, 5);
    close(r.frictionFactor, 0.01641, 0.0001);
    close(r.headlossM, 1.0598, 0.001);
  });
  it("minor loss", () => {
    const r = calc.minorLoss(0.05, 0.2, 1.5);
    close(r.velocityMs, 1.5915, 0.001);
    close(r.headlossM, 0.19372, 0.0005);
    expect(() => calc.minorLoss(0.05, 0.2, -0.5)).toThrow(InputError);
  });
  it("pump power", () => {
    const r = calc.pumpPower(0.05, 20, 75);
    close(r.hydraulicPowerKw, 9.80665, 0.001);
    close(r.inputPowerKw, 13.0755, 0.001);
  });
  it("detention", () => close(calc.constantFlowDetention(0.2, 0.1, 30).storageM3, 180, 0.001));
  it("buoyancy", () => {
    const r = calc.pipeBuoyancy(0.55, 0.45, 1, 2400, 0.75, 10);
    expect(r.buoyantForceKn).toBeGreaterThan(0);
    expect(Number.isFinite(r.factorOfSafety)).toBe(true);
  });
  it("rejects invalid geometry", () => {
    expect(() => calc.partFullCircularPipe(0.45, 0.55, 0.013, 0.005)).toThrow(InputError);
    expect(() => calc.pipeBuoyancy(0.45, 0.55, 1, 2400, 0.75, 10)).toThrow(InputError);
  });
});

describe("catalogue", () => {
  it("keeps the calculator ids saved calculations already use", () => {
    expect(CALCULATORS.map((c) => c.id).sort()).toEqual(
      ["buoyancy", "criticalDepth", "darcyWeisbach", "detention", "fullPipe", "hazenWilliams", "minimumGrade", "minorLoss", "orifice", "partFullPipe", "pumpPower", "rationalMethod", "rectangularChannel", "trapezoidalChannel", "weir"],
    );
  });
  it("every calculator runs on its defaults", () => {
    for (const c of CALCULATORS) {
      const raw = Object.fromEntries(c.fields.map((f) => [f.key, f.initial]));
      expect(run(c, raw).results.length, c.id).toBeGreaterThan(0);
    }
  });
  it("formats results and input labels like the Flutter app", () => {
    const fp = CALCULATOR_BY_ID.fullPipe;
    expect(run(fp, { d: "0.45", n: "0.013", s: "0.005" }).results).toEqual([
      { label: "Flow", value: "0.202 m³/s" },
      { label: "Flow", value: "202 L/s" },
      { label: "Velocity", value: "1.27 m/s" },
    ]);
    expect(fieldLabel(fp.fields[0])).toBe("Internal diameter (m)");
    expect(fieldLabel(fp.fields[1])).toBe("Manning n");
    expect(() => run(fp, { d: "abc", n: "0.013", s: "0.005" })).toThrow("Internal diameter must be a number");
  });
});
