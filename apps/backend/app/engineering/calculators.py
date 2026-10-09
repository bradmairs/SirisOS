"""The civil/water calculators, server-side (ADR 110): a line-for-line port of
apps/web/src/engineering/calculators.ts so SirisAI can run them (by voice,
in chat) and get exactly what the Calculators screen shows.

Parity is tested, not hoped for: apps/web/src/engineering/calculator-cases.json
holds inputs and the TypeScript results, written by the web test suite, and
tests/test_calculators.py runs the same cases through this module. Change a
formula in one place without the other and one of the two suites fails.
Results are formatted like JavaScript's Number.prototype.toFixed (round half
up on the exact binary value), not Python's round-half-even.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable

G = 9.80665


class InputError(ValueError):
    pass


def _positive(value: float, name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise InputError(f"{name} must be greater than zero")


def _non_negative(value: float, name: str) -> None:
    if not math.isfinite(value) or value < 0:
        raise InputError(f"{name} must be zero or more")


def fixed(n: float, digits: int) -> str:
    """JavaScript's n.toFixed(digits)."""
    if math.isnan(n):
        return "NaN"
    if math.isinf(n):
        return "Infinity" if n > 0 else "-Infinity"
    if abs(n) >= 1e21:
        return repr(n)
    if n == 0:
        n = 0.0  # -0 prints as "0.00" in JavaScript; -0.0001 still prints "-0.00"
    return str(Decimal(n).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def _manning(area: float, radius: float, n: float, slope: float) -> dict[str, float]:
    flow = (1 / n) * area * radius ** (2 / 3) * math.sqrt(slope)
    return {"flow": flow, "velocity": flow / area, "area": area, "radius": radius}


def full_circular_pipe(d: float, n: float, s: float) -> dict[str, float]:
    _positive(d, "diameter"); _positive(n, "roughness"); _positive(s, "slope")
    return _manning(math.pi * d * d / 4, d / 4, n, s)


def part_full_circular_pipe(d: float, y: float, n: float, s: float) -> dict[str, float]:
    _positive(d, "diameter"); _positive(y, "depth"); _positive(n, "roughness"); _positive(s, "slope")
    if y > d:
        raise InputError("depth cannot exceed diameter")
    r = d / 2
    theta = 2 * math.acos((r - y) / r)
    area = r * r * (theta - math.sin(theta)) / 2
    return _manning(area, area / (r * theta), n, s)


def minimum_circular_pipe_grade(d: float, n: float, q: float) -> dict[str, float]:
    _positive(d, "diameter"); _positive(n, "roughness"); _positive(q, "targetFlow")
    area = math.pi * d * d / 4
    slope = ((q * n) / (area * (d / 4) ** (2 / 3))) ** 2
    return {"slope": slope, "grade_percent": slope * 100}


def rectangular_channel(b: float, y: float, n: float, s: float) -> dict[str, float]:
    _positive(b, "width"); _positive(y, "depth"); _positive(n, "roughness"); _positive(s, "slope")
    area = b * y
    return _manning(area, area / (b + 2 * y), n, s)


def trapezoidal_channel(b: float, y: float, z: float, n: float, s: float) -> dict[str, float]:
    _positive(b, "bottomWidth"); _positive(y, "depth"); _non_negative(z, "sideSlope"); _positive(n, "roughness"); _positive(s, "slope")
    area = y * (b + z * y)
    return _manning(area, area / (b + 2 * y * math.sqrt(1 + z * z)), n, s)


def rectangular_critical_depth(q: float, b: float) -> dict[str, float]:
    _positive(q, "flow"); _positive(b, "width")
    depth = ((q * q) / (G * b * b)) ** (1 / 3)
    return {"depth": depth, "velocity": q / (b * depth)}


def rational_method(c: float, i: float, a: float) -> dict[str, float]:
    if not (0 <= c <= 1):
        raise InputError("runoffCoefficient must be between 0 and 1")
    _positive(i, "intensity"); _positive(a, "area")
    return {"flow": c * i * a / 360}


def rectangular_weir(cd: float, b: float, h: float) -> dict[str, float]:
    _positive(cd, "dischargeCoefficient"); _positive(b, "width"); _positive(h, "head")
    return {"flow": (2 / 3) * cd * b * math.sqrt(2 * G) * h ** 1.5}


def circular_orifice(cd: float, d: float, h: float) -> dict[str, float]:
    _positive(cd, "dischargeCoefficient"); _positive(d, "diameter"); _positive(h, "head")
    velocity = cd * math.sqrt(2 * G * h)
    return {"flow": math.pi * d * d / 4 * velocity, "velocity": velocity}


def hazen_williams(q: float, d: float, length: float, c: float) -> dict[str, float]:
    _positive(q, "flow"); _positive(d, "diameter"); _positive(length, "length"); _positive(c, "coefficientC")
    headloss = 10.67 * length * q ** 1.852 / (c ** 1.852 * d ** 4.87)
    return {"headloss": headloss, "velocity": q / (math.pi * d * d / 4)}


def darcy_weisbach(q: float, d: float, length: float, roughness_mm: float, nu: float = 1.004e-6) -> dict[str, float]:
    _positive(q, "flow"); _positive(d, "diameter"); _positive(length, "length"); _non_negative(roughness_mm, "roughness"); _positive(nu, "kinematicViscosity")
    velocity = q / (math.pi * d * d / 4)
    reynolds = velocity * d / nu
    rel = roughness_mm / 1000 / d
    f = 64 / reynolds if reynolds < 2300 else 0.25 / math.log10(rel / 3.7 + 5.74 / reynolds ** 0.9) ** 2
    return {"headloss": f * (length / d) * velocity * velocity / (2 * G), "velocity": velocity, "reynolds": reynolds, "friction": f}


def minor_loss(q: float, d: float, k: float) -> dict[str, float]:
    _positive(q, "flow"); _positive(d, "diameter"); _non_negative(k, "sumKValues")
    velocity = q / (math.pi * d * d / 4)
    return {"headloss": k * velocity * velocity / (2 * G), "velocity": velocity}


def pump_power(q: float, h: float, efficiency_percent: float, density: float = 1000) -> dict[str, float]:
    _positive(q, "flow"); _positive(h, "totalHead"); _positive(density, "fluidDensity")
    if not (0 < efficiency_percent <= 100):
        raise InputError("efficiencyPercent must be > 0 and <= 100")
    hydraulic = density * G * q * h / 1000
    return {"hydraulic_kw": hydraulic, "input_kw": hydraulic / (efficiency_percent / 100)}


def pipe_buoyancy(od: float, inner: float, length: float, pipe_density: float, cover: float, soil_unit_weight: float, water_density: float = 1000) -> dict[str, float]:
    _positive(od, "outsideDiameter"); _positive(inner, "insideDiameter"); _positive(length, "length"); _positive(pipe_density, "pipeDensity")
    if inner >= od:
        raise InputError("insideDiameter must be less than outsideDiameter")
    _non_negative(cover, "soilCover"); _non_negative(soil_unit_weight, "submergedSoilUnitWeight")
    buoyant = water_density * G * (math.pi * od * od / 4) * length / 1000
    pipe = pipe_density * G * (math.pi * (od * od - inner * inner) / 4) * length / 1000
    soil = soil_unit_weight * od * cover * length
    resisting = pipe + soil
    return {"buoyant": buoyant, "resisting": resisting, "fos": math.inf if buoyant == 0 else resisting / buoyant}


def constant_flow_detention(qi: float, qo: float, minutes: float) -> dict[str, float]:
    _non_negative(qi, "inflow"); _non_negative(qo, "allowableOutflow"); _positive(minutes, "duration")
    return {"inflow": qi, "outflow": qo, "storage": max(0, qi - qo) * minutes * 60}


# -- the catalogue ----------------------------------------------------------------


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    unit: str
    initial: str


@dataclass(frozen=True)
class Calculator:
    id: str
    title: str
    category: str
    note: str
    fields: tuple[Field, ...]
    compute: Callable[[dict[str, float]], list[dict[str, str]]]

    def describe(self) -> dict:
        return {"id": self.id, "title": self.title, "category": self.category, "note": self.note,
                "fields": [{"key": f.key, "label": f.label, "unit": f.unit, "initial": f.initial} for f in self.fields]}


def _f(key: str, label: str, unit: str, initial: str) -> Field:
    return Field(key, label, unit, initial)


def _r(label: str, value: str) -> dict[str, str]:
    return {"label": label, "value": value}


def _flow(q: float, v: float) -> list[dict[str, str]]:
    return [_r("Flow", f"{fixed(q, 3)} m³/s"), _r("Flow", f"{fixed(q * 1000, 0)} L/s"), _r("Velocity", f"{fixed(v, 2)} m/s")]


def _discharge(q: float) -> list[dict[str, str]]:
    return [_r("Discharge", f"{fixed(q, 3)} m³/s"), _r("Discharge", f"{fixed(q * 1000, 0)} L/s")]


def _min_grade(v: dict[str, float]) -> list[dict[str, str]]:
    r = minimum_circular_pipe_grade(v["d"], v["n"], v["q"])
    return [_r("Required slope", fixed(r["slope"], 5)), _r("Required grade", f"{fixed(r['grade_percent'], 3)}%"), _r("Equivalent", f"1 in {fixed(1 / r['slope'], 0)}")]


def _detention(v: dict[str, float]) -> list[dict[str, str]]:
    r = constant_flow_detention(v["qi"], v["qo"], v["t"])
    return [_r("Required storage", f"{fixed(r['storage'], 1)} m³"), _r("Excess flow", f"{fixed(max(0, r['inflow'] - r['outflow']) * 1000, 0)} L/s")]


def _darcy(v: dict[str, float]) -> list[dict[str, str]]:
    r = darcy_weisbach(v["q"], v["d"], v["l"], v["e"])
    return [_r("Friction headloss", f"{fixed(r['headloss'], 2)} m"), _r("Velocity", f"{fixed(r['velocity'], 2)} m/s"),
            _r("Reynolds number", fixed(r["reynolds"], 0)), _r("Darcy friction factor", fixed(r["friction"], 4))]


def _buoyancy(v: dict[str, float]) -> list[dict[str, str]]:
    r = pipe_buoyancy(v["od"], v["id"], v["l"], v["pd"], v["c"], v["g"])
    return [_r("Buoyant force", f"{fixed(r['buoyant'], 1)} kN"), _r("Resisting force", f"{fixed(r['resisting'], 1)} kN"),
            _r("Factor of safety", fixed(r["fos"], 2)), _r("Screening result", "Resisting > uplift" if r["fos"] >= 1 else "Uplift exceeds resistance")]


CALCULATORS: list[Calculator] = [
    Calculator("fullPipe", "Full pipe Manning", "Stormwater & pipes", "Steady, uniform, full circular pipe flow using Manning’s equation.",
               (_f("d", "Internal diameter", "m", "0.45"), _f("n", "Manning n", "", "0.013"), _f("s", "Hydraulic grade", "m/m", "0.005")),
               lambda v: (lambda r: _flow(r["flow"], r["velocity"]))(full_circular_pipe(v["d"], v["n"], v["s"]))),
    Calculator("partFullPipe", "Part-full pipe Manning", "Stormwater & pipes", "Circular-pipe flow at a specified water depth. Useful for gravity pipe checks below full depth.",
               (_f("d", "Internal diameter", "m", "0.60"), _f("y", "Flow depth", "m", "0.30"), _f("n", "Manning n", "", "0.013"), _f("s", "Hydraulic grade", "m/m", "0.005")),
               lambda v: (lambda r: [*_flow(r["flow"], r["velocity"]), _r("Flow area", f"{fixed(r['area'], 3)} m²")])(part_full_circular_pipe(v["d"], v["y"], v["n"], v["s"]))),
    Calculator("minimumGrade", "Minimum pipe grade", "Stormwater & pipes", "Solves Manning’s equation for the grade required to carry a target full-pipe flow.",
               (_f("d", "Internal diameter", "m", "0.45"), _f("n", "Manning n", "", "0.013"), _f("q", "Target flow", "m³/s", "0.20")), _min_grade),
    Calculator("rectangularChannel", "Rectangular channel", "Open channels", "Manning capacity for a rectangular open channel under steady uniform flow.",
               (_f("b", "Channel width", "m", "1.0"), _f("y", "Flow depth", "m", "0.30"), _f("n", "Manning n", "", "0.015"), _f("s", "Channel grade", "m/m", "0.005")),
               lambda v: (lambda r: _flow(r["flow"], r["velocity"]))(rectangular_channel(v["b"], v["y"], v["n"], v["s"]))),
    Calculator("trapezoidalChannel", "Trapezoidal channel", "Open channels", "Manning capacity for a trapezoidal channel using horizontal:vertical side slopes.",
               (_f("b", "Bottom width", "m", "1.0"), _f("y", "Flow depth", "m", "0.50"), _f("z", "Side slope H:V", "", "2.0"), _f("n", "Manning n", "", "0.030"), _f("s", "Channel grade", "m/m", "0.005")),
               lambda v: (lambda r: [*_flow(r["flow"], r["velocity"]), _r("Flow area", f"{fixed(r['area'], 3)} m²")])(trapezoidal_channel(v["b"], v["y"], v["z"], v["n"], v["s"]))),
    Calculator("criticalDepth", "Rectangular critical depth", "Open channels", "Critical depth and velocity for a rectangular channel at a specified discharge.",
               (_f("q", "Flow", "m³/s", "0.50"), _f("b", "Channel width", "m", "1.0")),
               lambda v: (lambda r: [_r("Critical depth", f"{fixed(r['depth'], 3)} m"), _r("Critical velocity", f"{fixed(r['velocity'], 2)} m/s")])(rectangular_critical_depth(v["q"], v["b"]))),
    Calculator("rationalMethod", "Rational Method", "Hydrology", "Peak flow using Q = C i A, with rainfall intensity in mm/h and area in hectares.",
               (_f("c", "Runoff coefficient C", "0–1", "0.8"), _f("i", "Rainfall intensity", "mm/h", "100"), _f("a", "Catchment area", "ha", "1.0")),
               lambda v: (lambda r: [_r("Peak flow", f"{fixed(r['flow'], 3)} m³/s"), _r("Peak flow", f"{fixed(r['flow'] * 1000, 0)} L/s")])(rational_method(v["c"], v["i"], v["a"]))),
    Calculator("detention", "Detention storage", "Hydrology", "Screening storage from constant inflow minus allowable outflow over a selected duration.",
               (_f("qi", "Peak inflow", "m³/s", "0.20"), _f("qo", "Allowable outflow", "m³/s", "0.10"), _f("t", "Critical duration", "min", "30")), _detention),
    Calculator("weir", "Rectangular weir", "Structures & controls", "Free-flow rectangular sharp-crested weir equation using an entered discharge coefficient.",
               (_f("cd", "Discharge coefficient Cd", "", "0.62"), _f("b", "Weir width", "m", "1.0"), _f("h", "Head above crest", "m", "0.30")),
               lambda v: _discharge(rectangular_weir(v["cd"], v["b"], v["h"])["flow"])),
    Calculator("orifice", "Circular orifice", "Structures & controls", "Free discharge through a circular orifice under a specified head.",
               (_f("cd", "Discharge coefficient Cd", "", "0.62"), _f("d", "Orifice diameter", "m", "0.15"), _f("h", "Head to orifice centre", "m", "1.0")),
               lambda v: (lambda r: [*_discharge(r["flow"]), _r("Jet velocity", f"{fixed(r['velocity'], 2)} m/s")])(circular_orifice(v["cd"], v["d"], v["h"]))),
    Calculator("hazenWilliams", "Hazen–Williams headloss", "Pressure pipes", "SI Hazen–Williams friction headloss. Use an appropriate C value for the pipe material and condition.",
               (_f("q", "Flow", "m³/s", "0.05"), _f("d", "Internal diameter", "m", "0.20"), _f("l", "Pipe length", "m", "100"), _f("c", "Hazen–Williams C", "", "140")),
               lambda v: (lambda r: [_r("Friction headloss", f"{fixed(r['headloss'], 2)} m"), _r("Velocity", f"{fixed(r['velocity'], 2)} m/s")])(hazen_williams(v["q"], v["d"], v["l"], v["c"]))),
    Calculator("darcyWeisbach", "Darcy–Weisbach headloss", "Pressure pipes", "Pipe friction using Reynolds number and Swamee–Jain for turbulent flow; water viscosity defaults near 20 °C.",
               (_f("q", "Flow", "m³/s", "0.05"), _f("d", "Internal diameter", "m", "0.20"), _f("l", "Pipe length", "m", "100"), _f("e", "Absolute roughness", "mm", "0.045")), _darcy),
    Calculator("minorLoss", "Minor loss (K-value)", "Pressure pipes", "Fitting/valve/bend headloss from an entered sum of K coefficients. Enter K values from your governing standard or manufacturer data — none are assumed.",
               (_f("q", "Flow", "m³/s", "0.05"), _f("d", "Internal diameter", "m", "0.20"), _f("k", "Sum of K values", "", "1.5")),
               lambda v: (lambda r: [_r("Minor headloss", f"{fixed(r['headloss'], 3)} m"), _r("Velocity", f"{fixed(r['velocity'], 2)} m/s")])(minor_loss(v["q"], v["d"], v["k"]))),
    Calculator("pumpPower", "Pump power", "Pressure pipes", "Hydraulic and estimated input power from flow, total dynamic head and pump efficiency.",
               (_f("q", "Flow", "m³/s", "0.05"), _f("h", "Total dynamic head", "m", "20"), _f("e", "Pump efficiency", "%", "75")),
               lambda v: (lambda r: [_r("Hydraulic power", f"{fixed(r['hydraulic_kw'], 2)} kW"), _r("Estimated input power", f"{fixed(r['input_kw'], 2)} kW")])(pump_power(v["q"], v["h"], v["e"]))),
    Calculator("buoyancy", "Buried pipe buoyancy", "Pipe design checks", "Screening check for full submergence. Excludes side shear, anchors, slabs and project-specific load factors.",
               (_f("od", "Outside diameter", "m", "0.55"), _f("id", "Inside diameter", "m", "0.45"), _f("l", "Pipe length checked", "m", "1.0"),
                _f("pd", "Pipe material density", "kg/m³", "2400"), _f("c", "Soil cover above crown", "m", "0.75"), _f("g", "Submerged soil unit weight", "kN/m³", "10")), _buoyancy),
]

BY_ID: dict[str, Calculator] = {c.id: c for c in CALCULATORS}


def run(calculator_id: str, inputs: dict[str, float]) -> dict:
    """Run one calculator. Raises KeyError for an unknown id and InputError
    for a missing, non-numeric or out-of-range input."""
    calculator = BY_ID[calculator_id]
    values: dict[str, float] = {}
    for field in calculator.fields:
        raw = inputs.get(field.key)
        if raw is None or isinstance(raw, bool):
            raise InputError(f"{field.label} ({field.key}) is required")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise InputError(f"{field.label} must be a number") from None
        if not math.isfinite(value):
            raise InputError(f"{field.label} must be a number")
        values[field.key] = value
    return {"calculator": calculator.id, "title": calculator.title, "inputs": values, "results": calculator.compute(values)}
