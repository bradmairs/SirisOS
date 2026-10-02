/** Deterministic civil/water calculators, ported from the Flutter
 * EngineeringCalculators library. Calculator ids match the ones already
 * stored on saved calculations (the Dart enum names). SI units throughout. */

const G = 9.80665;

export class InputError extends Error {}

function positive(value: number, name: string) {
  if (!Number.isFinite(value) || value <= 0) throw new InputError(`${name} must be greater than zero`);
}
function nonNegative(value: number, name: string) {
  if (!Number.isFinite(value) || value < 0) throw new InputError(`${name} must be zero or more`);
}

export interface Manning {
  flowM3s: number;
  velocityMs: number;
  areaM2: number;
  hydraulicRadiusM: number;
}

function manning(area: number, radius: number, n: number, slope: number): Manning {
  const flow = (1 / n) * area * Math.pow(radius, 2 / 3) * Math.sqrt(slope);
  return { flowM3s: flow, velocityMs: flow / area, areaM2: area, hydraulicRadiusM: radius };
}

export const calc = {
  fullCircularPipe(d: number, n: number, s: number): Manning {
    positive(d, "diameter"); positive(n, "roughness"); positive(s, "slope");
    return manning((Math.PI * d * d) / 4, d / 4, n, s);
  },
  partFullCircularPipe(d: number, y: number, n: number, s: number): Manning {
    positive(d, "diameter"); positive(y, "depth"); positive(n, "roughness"); positive(s, "slope");
    if (y > d) throw new InputError("depth cannot exceed diameter");
    const r = d / 2;
    const theta = 2 * Math.acos((r - y) / r);
    const area = (r * r * (theta - Math.sin(theta))) / 2;
    return manning(area, area / (r * theta), n, s);
  },
  minimumCircularPipeGrade(d: number, n: number, q: number) {
    positive(d, "diameter"); positive(n, "roughness"); positive(q, "targetFlow");
    const area = (Math.PI * d * d) / 4;
    const slope = Math.pow((q * n) / (area * Math.pow(d / 4, 2 / 3)), 2);
    return { slope, gradePercent: slope * 100 };
  },
  rectangularChannel(b: number, y: number, n: number, s: number): Manning {
    positive(b, "width"); positive(y, "depth"); positive(n, "roughness"); positive(s, "slope");
    const area = b * y;
    return manning(area, area / (b + 2 * y), n, s);
  },
  trapezoidalChannel(b: number, y: number, z: number, n: number, s: number): Manning {
    positive(b, "bottomWidth"); positive(y, "depth"); nonNegative(z, "sideSlope"); positive(n, "roughness"); positive(s, "slope");
    const area = y * (b + z * y);
    return manning(area, area / (b + 2 * y * Math.sqrt(1 + z * z)), n, s);
  },
  rectangularCriticalDepth(q: number, b: number) {
    positive(q, "flow"); positive(b, "width");
    const depth = Math.cbrt((q * q) / (G * b * b));
    return { depthM: depth, velocityMs: q / (b * depth) };
  },
  rationalMethod(c: number, i: number, a: number) {
    if (!(c >= 0 && c <= 1)) throw new InputError("runoffCoefficient must be between 0 and 1");
    positive(i, "intensity"); positive(a, "area");
    return { flowM3s: (c * i * a) / 360 };
  },
  rectangularWeir(cd: number, b: number, h: number) {
    positive(cd, "dischargeCoefficient"); positive(b, "width"); positive(h, "head");
    return { flowM3s: (2 / 3) * cd * b * Math.sqrt(2 * G) * Math.pow(h, 1.5) };
  },
  circularOrifice(cd: number, d: number, h: number) {
    positive(cd, "dischargeCoefficient"); positive(d, "diameter"); positive(h, "head");
    const velocity = cd * Math.sqrt(2 * G * h);
    return { flowM3s: ((Math.PI * d * d) / 4) * velocity, velocityMs: velocity };
  },
  hazenWilliams(q: number, d: number, l: number, c: number) {
    positive(q, "flow"); positive(d, "diameter"); positive(l, "length"); positive(c, "coefficientC");
    const headloss = (10.67 * l * Math.pow(q, 1.852)) / (Math.pow(c, 1.852) * Math.pow(d, 4.87));
    return { headlossM: headloss, velocityMs: q / ((Math.PI * d * d) / 4) };
  },
  darcyWeisbach(q: number, d: number, l: number, roughnessMm: number, nu = 1.004e-6) {
    positive(q, "flow"); positive(d, "diameter"); positive(l, "length"); nonNegative(roughnessMm, "roughness"); positive(nu, "kinematicViscosity");
    const velocity = q / ((Math.PI * d * d) / 4);
    const reynolds = (velocity * d) / nu;
    const rel = roughnessMm / 1000 / d;
    const f = reynolds < 2300 ? 64 / reynolds : 0.25 / Math.pow(Math.log10(rel / 3.7 + 5.74 / Math.pow(reynolds, 0.9)), 2);
    return { headlossM: (f * (l / d) * velocity * velocity) / (2 * G), velocityMs: velocity, reynoldsNumber: reynolds, frictionFactor: f };
  },
  minorLoss(q: number, d: number, k: number) {
    positive(q, "flow"); positive(d, "diameter"); nonNegative(k, "sumKValues");
    const velocity = q / ((Math.PI * d * d) / 4);
    return { headlossM: (k * velocity * velocity) / (2 * G), velocityMs: velocity };
  },
  pumpPower(q: number, h: number, efficiencyPercent: number, density = 1000) {
    positive(q, "flow"); positive(h, "totalHead"); positive(density, "fluidDensity");
    if (!(efficiencyPercent > 0 && efficiencyPercent <= 100)) throw new InputError("efficiencyPercent must be > 0 and <= 100");
    const hydraulicKw = (density * G * q * h) / 1000;
    return { hydraulicPowerKw: hydraulicKw, inputPowerKw: hydraulicKw / (efficiencyPercent / 100) };
  },
  pipeBuoyancy(od: number, id: number, l: number, pipeDensity: number, cover: number, soilUnitWeight: number, waterDensity = 1000) {
    positive(od, "outsideDiameter"); positive(id, "insideDiameter"); positive(l, "length"); positive(pipeDensity, "pipeDensity");
    if (id >= od) throw new InputError("insideDiameter must be less than outsideDiameter");
    nonNegative(cover, "soilCover"); nonNegative(soilUnitWeight, "submergedSoilUnitWeight");
    const buoyant = (waterDensity * G * ((Math.PI * od * od) / 4) * l) / 1000;
    const pipe = (pipeDensity * G * ((Math.PI * (od * od - id * id)) / 4) * l) / 1000;
    const soil = soilUnitWeight * od * cover * l;
    const resisting = pipe + soil;
    return { buoyantForceKn: buoyant, pipeWeightKn: pipe, soilWeightKn: soil, resistingForceKn: resisting, factorOfSafety: buoyant === 0 ? Infinity : resisting / buoyant };
  },
  constantFlowDetention(qi: number, qo: number, minutes: number) {
    nonNegative(qi, "inflow"); nonNegative(qo, "allowableOutflow"); positive(minutes, "duration");
    return { inflowM3s: qi, outflowM3s: qo, storageM3: Math.max(0, qi - qo) * minutes * 60 };
  },
};

// ---------------------------------------------------------------------------
// Calculator catalogue: what the UI renders and what a saved calculation stores.

export interface Field {
  key: string;
  label: string;
  unit: string;
  initial: string;
}

export interface Result {
  label: string;
  value: string;
}

export interface Calculator {
  id: string;
  title: string;
  category: string;
  note: string;
  fields: Field[];
  compute: (v: Record<string, number>) => Result[];
}

const f = (key: string, label: string, unit: string, initial: string): Field => ({ key, label, unit, initial });
const fixed = (n: number, digits: number) => n.toFixed(digits);
const flowResults = (q: number, v: number): Result[] => [
  { label: "Flow", value: `${fixed(q, 3)} m³/s` },
  { label: "Flow", value: `${fixed(q * 1000, 0)} L/s` },
  { label: "Velocity", value: `${fixed(v, 2)} m/s` },
];
const dischargeResults = (q: number): Result[] => [
  { label: "Discharge", value: `${fixed(q, 3)} m³/s` },
  { label: "Discharge", value: `${fixed(q * 1000, 0)} L/s` },
];

export const CALCULATORS: Calculator[] = [
  {
    id: "fullPipe", title: "Full pipe Manning", category: "Stormwater & pipes",
    note: "Steady, uniform, full circular pipe flow using Manning’s equation.",
    fields: [f("d", "Internal diameter", "m", "0.45"), f("n", "Manning n", "", "0.013"), f("s", "Hydraulic grade", "m/m", "0.005")],
    compute: (v) => { const r = calc.fullCircularPipe(v.d, v.n, v.s); return flowResults(r.flowM3s, r.velocityMs); },
  },
  {
    id: "partFullPipe", title: "Part-full pipe Manning", category: "Stormwater & pipes",
    note: "Circular-pipe flow at a specified water depth. Useful for gravity pipe checks below full depth.",
    fields: [f("d", "Internal diameter", "m", "0.60"), f("y", "Flow depth", "m", "0.30"), f("n", "Manning n", "", "0.013"), f("s", "Hydraulic grade", "m/m", "0.005")],
    compute: (v) => { const r = calc.partFullCircularPipe(v.d, v.y, v.n, v.s); return [...flowResults(r.flowM3s, r.velocityMs), { label: "Flow area", value: `${fixed(r.areaM2, 3)} m²` }]; },
  },
  {
    id: "minimumGrade", title: "Minimum pipe grade", category: "Stormwater & pipes",
    note: "Solves Manning’s equation for the grade required to carry a target full-pipe flow.",
    fields: [f("d", "Internal diameter", "m", "0.45"), f("n", "Manning n", "", "0.013"), f("q", "Target flow", "m³/s", "0.20")],
    compute: (v) => {
      const r = calc.minimumCircularPipeGrade(v.d, v.n, v.q);
      return [
        { label: "Required slope", value: fixed(r.slope, 5) },
        { label: "Required grade", value: `${fixed(r.gradePercent, 3)}%` },
        { label: "Equivalent", value: `1 in ${fixed(1 / r.slope, 0)}` },
      ];
    },
  },
  {
    id: "rectangularChannel", title: "Rectangular channel", category: "Open channels",
    note: "Manning capacity for a rectangular open channel under steady uniform flow.",
    fields: [f("b", "Channel width", "m", "1.0"), f("y", "Flow depth", "m", "0.30"), f("n", "Manning n", "", "0.015"), f("s", "Channel grade", "m/m", "0.005")],
    compute: (v) => { const r = calc.rectangularChannel(v.b, v.y, v.n, v.s); return flowResults(r.flowM3s, r.velocityMs); },
  },
  {
    id: "trapezoidalChannel", title: "Trapezoidal channel", category: "Open channels",
    note: "Manning capacity for a trapezoidal channel using horizontal:vertical side slopes.",
    fields: [f("b", "Bottom width", "m", "1.0"), f("y", "Flow depth", "m", "0.50"), f("z", "Side slope H:V", "", "2.0"), f("n", "Manning n", "", "0.030"), f("s", "Channel grade", "m/m", "0.005")],
    compute: (v) => { const r = calc.trapezoidalChannel(v.b, v.y, v.z, v.n, v.s); return [...flowResults(r.flowM3s, r.velocityMs), { label: "Flow area", value: `${fixed(r.areaM2, 3)} m²` }]; },
  },
  {
    id: "criticalDepth", title: "Rectangular critical depth", category: "Open channels",
    note: "Critical depth and velocity for a rectangular channel at a specified discharge.",
    fields: [f("q", "Flow", "m³/s", "0.50"), f("b", "Channel width", "m", "1.0")],
    compute: (v) => { const r = calc.rectangularCriticalDepth(v.q, v.b); return [{ label: "Critical depth", value: `${fixed(r.depthM, 3)} m` }, { label: "Critical velocity", value: `${fixed(r.velocityMs, 2)} m/s` }]; },
  },
  {
    id: "rationalMethod", title: "Rational Method", category: "Hydrology",
    note: "Peak flow using Q = C i A, with rainfall intensity in mm/h and area in hectares.",
    fields: [f("c", "Runoff coefficient C", "0–1", "0.8"), f("i", "Rainfall intensity", "mm/h", "100"), f("a", "Catchment area", "ha", "1.0")],
    compute: (v) => { const r = calc.rationalMethod(v.c, v.i, v.a); return [{ label: "Peak flow", value: `${fixed(r.flowM3s, 3)} m³/s` }, { label: "Peak flow", value: `${fixed(r.flowM3s * 1000, 0)} L/s` }]; },
  },
  {
    id: "detention", title: "Detention storage", category: "Hydrology",
    note: "Screening storage from constant inflow minus allowable outflow over a selected duration.",
    fields: [f("qi", "Peak inflow", "m³/s", "0.20"), f("qo", "Allowable outflow", "m³/s", "0.10"), f("t", "Critical duration", "min", "30")],
    compute: (v) => {
      const r = calc.constantFlowDetention(v.qi, v.qo, v.t);
      return [{ label: "Required storage", value: `${fixed(r.storageM3, 1)} m³` }, { label: "Excess flow", value: `${fixed(Math.max(0, r.inflowM3s - r.outflowM3s) * 1000, 0)} L/s` }];
    },
  },
  {
    id: "weir", title: "Rectangular weir", category: "Structures & controls",
    note: "Free-flow rectangular sharp-crested weir equation using an entered discharge coefficient.",
    fields: [f("cd", "Discharge coefficient Cd", "", "0.62"), f("b", "Weir width", "m", "1.0"), f("h", "Head above crest", "m", "0.30")],
    compute: (v) => dischargeResults(calc.rectangularWeir(v.cd, v.b, v.h).flowM3s),
  },
  {
    id: "orifice", title: "Circular orifice", category: "Structures & controls",
    note: "Free discharge through a circular orifice under a specified head.",
    fields: [f("cd", "Discharge coefficient Cd", "", "0.62"), f("d", "Orifice diameter", "m", "0.15"), f("h", "Head to orifice centre", "m", "1.0")],
    compute: (v) => { const r = calc.circularOrifice(v.cd, v.d, v.h); return [...dischargeResults(r.flowM3s), { label: "Jet velocity", value: `${fixed(r.velocityMs, 2)} m/s` }]; },
  },
  {
    id: "hazenWilliams", title: "Hazen–Williams headloss", category: "Pressure pipes",
    note: "SI Hazen–Williams friction headloss. Use an appropriate C value for the pipe material and condition.",
    fields: [f("q", "Flow", "m³/s", "0.05"), f("d", "Internal diameter", "m", "0.20"), f("l", "Pipe length", "m", "100"), f("c", "Hazen–Williams C", "", "140")],
    compute: (v) => { const r = calc.hazenWilliams(v.q, v.d, v.l, v.c); return [{ label: "Friction headloss", value: `${fixed(r.headlossM, 2)} m` }, { label: "Velocity", value: `${fixed(r.velocityMs, 2)} m/s` }]; },
  },
  {
    id: "darcyWeisbach", title: "Darcy–Weisbach headloss", category: "Pressure pipes",
    note: "Pipe friction using Reynolds number and Swamee–Jain for turbulent flow; water viscosity defaults near 20 °C.",
    fields: [f("q", "Flow", "m³/s", "0.05"), f("d", "Internal diameter", "m", "0.20"), f("l", "Pipe length", "m", "100"), f("e", "Absolute roughness", "mm", "0.045")],
    compute: (v) => {
      const r = calc.darcyWeisbach(v.q, v.d, v.l, v.e);
      return [
        { label: "Friction headloss", value: `${fixed(r.headlossM, 2)} m` },
        { label: "Velocity", value: `${fixed(r.velocityMs, 2)} m/s` },
        { label: "Reynolds number", value: fixed(r.reynoldsNumber, 0) },
        { label: "Darcy friction factor", value: fixed(r.frictionFactor, 4) },
      ];
    },
  },
  {
    id: "minorLoss", title: "Minor loss (K-value)", category: "Pressure pipes",
    note: "Fitting/valve/bend headloss from an entered sum of K coefficients. Enter K values from your governing standard or manufacturer data — none are assumed.",
    fields: [f("q", "Flow", "m³/s", "0.05"), f("d", "Internal diameter", "m", "0.20"), f("k", "Sum of K values", "", "1.5")],
    compute: (v) => { const r = calc.minorLoss(v.q, v.d, v.k); return [{ label: "Minor headloss", value: `${fixed(r.headlossM, 3)} m` }, { label: "Velocity", value: `${fixed(r.velocityMs, 2)} m/s` }]; },
  },
  {
    id: "pumpPower", title: "Pump power", category: "Pressure pipes",
    note: "Hydraulic and estimated input power from flow, total dynamic head and pump efficiency.",
    fields: [f("q", "Flow", "m³/s", "0.05"), f("h", "Total dynamic head", "m", "20"), f("e", "Pump efficiency", "%", "75")],
    compute: (v) => { const r = calc.pumpPower(v.q, v.h, v.e); return [{ label: "Hydraulic power", value: `${fixed(r.hydraulicPowerKw, 2)} kW` }, { label: "Estimated input power", value: `${fixed(r.inputPowerKw, 2)} kW` }]; },
  },
  {
    id: "buoyancy", title: "Buried pipe buoyancy", category: "Pipe design checks",
    note: "Screening check for full submergence. Excludes side shear, anchors, slabs and project-specific load factors.",
    fields: [
      f("od", "Outside diameter", "m", "0.55"), f("id", "Inside diameter", "m", "0.45"), f("l", "Pipe length checked", "m", "1.0"),
      f("pd", "Pipe material density", "kg/m³", "2400"), f("c", "Soil cover above crown", "m", "0.75"), f("g", "Submerged soil unit weight", "kN/m³", "10"),
    ],
    compute: (v) => {
      const r = calc.pipeBuoyancy(v.od, v.id, v.l, v.pd, v.c, v.g);
      return [
        { label: "Buoyant force", value: `${fixed(r.buoyantForceKn, 1)} kN` },
        { label: "Resisting force", value: `${fixed(r.resistingForceKn, 1)} kN` },
        { label: "Factor of safety", value: fixed(r.factorOfSafety, 2) },
        { label: "Screening result", value: r.factorOfSafety >= 1 ? "Resisting > uplift" : "Uplift exceeds resistance" },
      ];
    },
  },
];

export const CALCULATOR_BY_ID: Record<string, Calculator> = Object.fromEntries(CALCULATORS.map((c) => [c.id, c]));

/** "Label (unit)", the key saved calculations already use for inputs. */
export function fieldLabel(field: Field): string {
  return field.unit ? `${field.label} (${field.unit})` : field.label;
}

/** Parse the raw field strings and run the calculator. */
export function run(calculator: Calculator, raw: Record<string, string>): { values: Record<string, number>; results: Result[] } {
  const values: Record<string, number> = {};
  for (const field of calculator.fields) {
    const text = (raw[field.key] ?? "").trim();
    const value = Number(text);
    if (text === "" || !Number.isFinite(value)) throw new InputError(`${field.label} must be a number`);
    values[field.key] = value;
  }
  return { values, results: calculator.compute(values) };
}
