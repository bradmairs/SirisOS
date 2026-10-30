"""The Health section's scores (5.7), each against your own recent normal
rather than a population average.

**Readiness** (0 to 100): how ready your body is to take on strain today.
- Heart rate variability against your last 30 days (35%): higher than your
  usual is good.
- Resting heart rate against your usual (20%): lower is good.
- Last night's sleep against what you need (30%): what you usually sleep,
  but at least 7 hours and no more than 9.
- Vitals (10%): respiratory rate a breath a minute over your usual, wrist
  temperature 0.5 °C over, or blood oxygen under 94% each count against you.
  Together they're an early sign of getting sick.
- Yesterday's load (5%): a much harder day than usual leaves you less fresh.
Missing parts are left out and the rest re-weighted; with neither HRV nor
sleep there's no score. 70 and over is **Primed**, 45 to 69 **Steady**, under
45 **Recover**. Until there are 7 days of history it's marked as early.

**Sleep score**: hours against need (60%), deep and REM sleep as a share of
the night (20%, when the watch records stages), and how regular your bedtime
has been this week (20%).

**Load**: your exercise minutes this week (acute) against the last four
weeks (chronic). 0.8 to 1.3 is the sweet spot; over 1.5 is a sharp jump.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import mean, pstdev
from typing import Any

Days = dict[str, dict[str, float]]

LABELS: dict[str, tuple[str, str]] = {
    "heart_rate_variability": ("HRV", "ms"),
    "resting_heart_rate": ("Resting heart rate", "bpm"),
    "sleep_hours": ("Sleep", "h"),
    "respiratory_rate": ("Respiratory rate", "/min"),
    "wrist_temperature": ("Wrist temperature", "°C"),
    "blood_oxygen": ("Blood oxygen", "%"),
    "vo2_max": ("VO₂ max", "ml/kg/min"),
    "walking_heart_rate": ("Walking heart rate", "bpm"),
    "weight_kg": ("Weight", "kg"),
    "body_fat_pct": ("Body fat", "%"),
    "steps": ("Steps", ""),
    "active_energy_kcal": ("Active energy", "kcal"),
    "exercise_minutes": ("Exercise", "min"),
}
VITALS = ["heart_rate_variability", "resting_heart_rate", "respiratory_rate", "blood_oxygen", "wrist_temperature",
          "walking_heart_rate", "vo2_max", "weight_kg", "body_fat_pct"]


def clamp(v: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, v))


def baseline(days: Days, metric: str, before: date, window: int = 30, minimum: int = 5) -> tuple[float, float] | None:
    start = (before - timedelta(days=window)).isoformat()
    vals = [float(m[metric]) for d, m in days.items() if start <= d < before.isoformat() and m.get(metric) is not None]
    if len(vals) < minimum:
        return None
    return mean(vals), pstdev(vals)


def latest(days: Days, metric: str, on: date, back: int = 1) -> tuple[str, float] | None:
    """Today's value, else the day before's (the morning's HRV may not be in yet)."""
    for i in range(back + 1):
        d = (on - timedelta(days=i)).isoformat()
        v = (days.get(d) or {}).get(metric)
        if v is not None:
            return d, float(v)
    return None


def sleep_need(days: Days, on: date) -> float:
    b = baseline(days, "sleep_hours", on, 30, 5)
    return round(min(9.0, max(7.0, b[0] if b else 7.5)), 2)


def _z(value: float, base: tuple[float, float], floor_share: float) -> float:
    mu, sd = base
    return (value - mu) / max(sd, abs(mu) * floor_share, 1e-6)


def readiness(days: Days, on: date) -> dict[str, Any] | None:
    parts: list[tuple[str, float, float, dict[str, Any]]] = []  # key, weight, score, detail
    history = sum(1 for d in days if d < on.isoformat())

    def add(key: str, weight: float, score: float, value: float | None, base: float | None, text: str) -> None:
        label, unit = LABELS.get(key, (key, ""))
        parts.append((key, weight, clamp(score), {"key": key, "label": label, "unit": unit, "value": value, "baseline": base,
                                                   "score": round(clamp(score)), "text": text}))

    hrv, base = latest(days, "heart_rate_variability", on), baseline(days, "heart_rate_variability", on)
    if hrv and base:
        z = _z(hrv[1], base, 0.08)
        add("heart_rate_variability", 0.35, 60 + 22 * z, round(hrv[1]), round(base[0]),
            f"HRV {hrv[1]:.0f} ms, {'above' if z > 0.3 else 'below' if z < -0.3 else 'around'} your usual {base[0]:.0f}")
    rhr, base = latest(days, "resting_heart_rate", on), baseline(days, "resting_heart_rate", on)
    if rhr and base:
        z = _z(rhr[1], base, 0.03)
        add("resting_heart_rate", 0.2, 60 - 22 * z, round(rhr[1]), round(base[0]),
            f"Resting heart rate {rhr[1]:.0f}, {'up on' if z > 0.3 else 'down on' if z < -0.3 else 'in line with'} your usual {base[0]:.0f}")
    sleep = latest(days, "sleep_hours", on, back=0)
    if sleep:
        need = sleep_need(days, on)
        ratio = sleep[1] / need
        add("sleep_hours", 0.3, (ratio - 0.6) / 0.4 * 100, round(sleep[1], 1), need,
            f"Slept {sleep[1]:.1f} h of the {need:.1f} h you need" if ratio < 0.95 else f"Slept {sleep[1]:.1f} h, enough")
    if not any(p[0] in ("heart_rate_variability", "sleep_hours") for p in parts):
        return None
    flags = []
    for key, limit, direction, text in (("respiratory_rate", 1.0, 1, "breathing faster than usual overnight"),
                                        ("wrist_temperature", 0.5, 1, "wrist temperature up overnight")):
        v, b = latest(days, key, on), baseline(days, key, on)
        if v and b and (v[1] - b[0]) * direction >= limit:
            flags.append(text)
    spo2 = latest(days, "blood_oxygen", on)
    if spo2 and spo2[1] < 94:
        flags.append(f"blood oxygen {spo2[1]:.0f}%")
    if any(latest(days, k, on) for k in ("respiratory_rate", "wrist_temperature", "blood_oxygen")):
        add("vitals", 0.1, 100 - 40 * len(flags), None, None, "Vitals normal" if not flags else "Watch out: " + ", ".join(flags))
    y = (on - timedelta(days=1))
    load_y, load_b = (days.get(y.isoformat()) or {}).get("exercise_minutes"), baseline(days, "exercise_minutes", y)
    if load_y is not None and load_b:
        z = _z(float(load_y), load_b, 0.25)
        add("load", 0.05, 100 if z < 1 else 100 - 30 * (z - 1), round(float(load_y)), round(load_b[0]),
            f"Yesterday {load_y:.0f} min of exercise" + (", a big day" if z >= 1.5 else ""))
    total = sum(w for _, w, _, _ in parts)
    score = round(sum(w * s for _, w, s, _ in parts) / total)
    band = "Primed" if score >= 70 else "Steady" if score >= 45 else "Recover"
    contributors = sorted((d for *_, d in parts), key=lambda d: d["score"])
    advice = {
        "Primed": "A good day to push: a hard session or a long run will land well.",
        "Steady": "Train as planned, but keep the hard efforts measured.",
        "Recover": "Go easy: a walk, mobility or rest. Hard training today costs more than it gives.",
    }[band]
    if flags:
        advice = "Your vitals suggest you might be coming down with something. Rest, drink water and see how tomorrow looks."
    return {"date": on.isoformat(), "score": score, "band": band, "advice": advice, "early": history < 7,
            "contributors": contributors, "summary": contributors[0]["text"] if contributors and contributors[0]["score"] < 50 else contributors[-1]["text"]}


def _minutes_after_6pm(stamp: str) -> float | None:
    try:
        t = datetime.fromisoformat(stamp.replace(" +", "+").replace(" -", "-")[:25].replace(" ", "T", 1))
    except ValueError:
        try:
            t = datetime.strptime(stamp[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    m = t.hour * 60 + t.minute - 18 * 60
    return m if m >= 0 else m + 24 * 60


def sleep(days: Days, times: dict[str, dict[str, str]], on: date, nights: int = 14) -> dict[str, Any]:
    need = sleep_need(days, on)
    out = []
    for i in range(nights - 1, -1, -1):
        d = (on - timedelta(days=i)).isoformat()
        m = days.get(d) or {}
        out.append({"date": d, "hours": m.get("sleep_hours"), "deep": m.get("sleep_deep_h"), "rem": m.get("sleep_rem_h"),
                    "core": m.get("sleep_core_h"), "awake": m.get("sleep_awake_h"), "in_bed": m.get("in_bed_h"),
                    "start": (times.get(d) or {}).get("start"), "end": (times.get(d) or {}).get("end")})
    last = out[-1] if out[-1]["hours"] else None
    week = [n for n in out[-7:] if n["hours"]]
    debt = round(sum(max(0.0, need - n["hours"]) for n in week), 1)
    starts = [x for n in out[-7:] if n["start"] and (x := _minutes_after_6pm(n["start"])) is not None]
    spread = pstdev(starts) if len(starts) >= 3 else None
    score = None
    if last:
        parts = [(0.6, min(1.0, last["hours"] / need))]
        if last["deep"] is not None and last["rem"] is not None and last["hours"]:
            parts.append((0.2, min(1.0, (last["deep"] + last["rem"]) / last["hours"] / 0.4)))
        if spread is not None:
            parts.append((0.2, 1 - min(1.0, spread / 90)))
        score = round(100 * sum(w * s for w, s in parts) / sum(w for w, _ in parts))
    return {"need": need, "last_night": last, "score": score, "debt_7d": debt, "bedtime_spread_min": round(spread) if spread is not None else None,
            "average_7d": round(mean(n["hours"] for n in week), 1) if week else None, "nights": out}


def load(days: Days, on: date) -> dict[str, Any]:
    def avg(n: int) -> float:
        return sum(float((days.get((on - timedelta(days=i)).isoformat()) or {}).get("exercise_minutes") or 0) for i in range(n)) / n
    acute, chronic = round(avg(7), 1), round(avg(28), 1)
    ratio = round(acute / chronic, 2) if chronic >= 5 else None
    zone = None if ratio is None else "low" if ratio < 0.8 else "sweet spot" if ratio <= 1.3 else "building" if ratio <= 1.5 else "spike"
    return {"acute_min_per_day": acute, "chronic_min_per_day": chronic, "ratio": ratio, "zone": zone}


def series(days: Days, metric: str, on: date, n: int = 30) -> list[dict[str, Any]]:
    return [{"date": (d := (on - timedelta(days=i)).isoformat()), "value": (days.get(d) or {}).get(metric)} for i in range(n - 1, -1, -1)]


def vitals(days: Days, on: date) -> list[dict[str, Any]]:
    out = []
    for key in VITALS:
        now = latest(days, key, on, back=7)
        if not now:
            continue
        base = baseline(days, key, on, 30, 5)
        state = "normal"
        if base and base[1] > 0 and abs(now[1] - base[0]) > 1.5 * max(base[1], abs(base[0]) * 0.02):
            state = "high" if now[1] > base[0] else "low"
        label, unit = LABELS[key]
        out.append({"key": key, "label": label, "unit": unit, "value": round(now[1], 1), "date": now[0],
                    "baseline": round(base[0], 1) if base else None, "spread": round(base[1], 1) if base else None,
                    "state": state, "series": series(days, key, on)})
    return out
