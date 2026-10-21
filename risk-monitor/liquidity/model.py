"""Pure calculations for the Korean liquidity-risk module.

The functions in this file have no network or filesystem side effects.  Every
historical score is calculated with data available at that point only.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def hp_trend(values: list[float], smoothing: float) -> list[float]:
    """Return the two-sided HP trend using an O(n) pentadiagonal LDLᵀ solve."""
    n = len(values)
    if n < 3:
        return list(values)
    if smoothing < 0 or any(not finite_number(value) for value in values):
        raise ValueError("HP input must contain finite values and a non-negative smoothing parameter")

    lam = float(smoothing)
    diagonal = [1.0 + 6.0 * lam] * n
    diagonal[0] = diagonal[-1] = 1.0 + lam
    if n == 3:
        diagonal[1] = 1.0 + 4.0 * lam
    else:
        diagonal[1] = diagonal[-2] = 1.0 + 5.0 * lam
    first = [-4.0 * lam] * (n - 1)
    first[0] = first[-1] = -2.0 * lam
    second = [lam] * (n - 2)

    # A = L D Lᵀ, where L has two non-zero sub-diagonals.
    d = [0.0] * n
    lower1 = [0.0] * n
    lower2 = [0.0] * n
    d[0] = diagonal[0]
    lower1[1] = first[0] / d[0]
    d[1] = diagonal[1] - lower1[1] * lower1[1] * d[0]
    for index in range(2, n):
        lower2[index] = second[index - 2] / d[index - 2]
        correction = lower2[index] * d[index - 2] * lower1[index - 1]
        lower1[index] = (first[index - 1] - correction) / d[index - 1]
        d[index] = (
            diagonal[index]
            - lower1[index] * lower1[index] * d[index - 1]
            - lower2[index] * lower2[index] * d[index - 2]
        )

    forward = [0.0] * n
    forward[0] = values[0]
    forward[1] = values[1] - lower1[1] * forward[0]
    for index in range(2, n):
        forward[index] = values[index] - lower1[index] * forward[index - 1] - lower2[index] * forward[index - 2]
    scaled = [forward[index] / d[index] for index in range(n)]
    trend = [0.0] * n
    trend[-1] = scaled[-1]
    trend[-2] = scaled[-2] - lower1[-1] * trend[-1]
    for index in range(n - 3, -1, -1):
        trend[index] = scaled[index] - lower1[index + 1] * trend[index + 1] - lower2[index + 2] * trend[index + 2]
    return trend


def one_sided_hp_gaps(
    observations: list[tuple[str, float]], smoothing: float, min_observations: int
) -> list[tuple[str, float]]:
    """Calculate endpoint log gaps on expanding samples; future data are never used."""
    clean = [(period, float(value)) for period, value in observations if finite_number(value) and value > 0]
    result: list[tuple[str, float]] = []
    logs = [math.log(value) for _, value in clean]
    for end in range(min_observations, len(clean) + 1):
        trend_endpoint = hp_trend(logs[:end], smoothing)[-1]
        gap = 100.0 * (logs[end - 1] - trend_endpoint)
        result.append((clean[end - 1][0], gap))
    return result


def expanding_percentiles(
    observations: list[tuple[str, float]], min_history: int
) -> list[dict[str, float | str]]:
    history: list[float] = []
    result: list[dict[str, float | str]] = []
    for period, value in observations:
        history.append(float(value))
        if len(history) < min_history:
            continue
        score = sum(item <= value for item in history) / len(history) * 100.0
        result.append({"period": period, "value": round(value, 6), "score": round(score, 4)})
    return result


def month_to_quarter(period: str) -> str:
    year, month = int(period[:4]), int(period[4:6])
    return f"{year}-Q{(month - 1) // 3 + 1}"


def quarter_end_month(period: str) -> str:
    year, quarter = period.split("-Q")
    return f"{year}{int(quarter) * 3:02d}"


def _series_map(rows: Iterable[dict]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        try:
            value = float(row["Value"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 0:
            result[row.get("Series", "")][row.get("Period", "")] = value
    return result


def _growth_percentiles(
    levels: dict[str, float], min_history: int
) -> dict[str, dict[str, float | str]]:
    periods = sorted(levels)
    growth: list[tuple[str, float]] = []
    for index in range(12, len(periods)):
        current_period, previous_period = periods[index], periods[index - 12]
        # A missing calendar month must not silently become a 12-observation comparison.
        year, month = int(current_period[:4]), int(current_period[4:6])
        expected = f"{year - 1}{month:02d}"
        if previous_period != expected:
            continue
        growth.append((current_period, 100.0 * math.log(levels[current_period] / levels[previous_period])))
    return {point["period"]: point for point in expanding_percentiles(growth, min_history)}


def build_signal(rows: list[dict], config: dict) -> dict:
    series = _series_map(rows)
    required = ("M2", "LF", "L", "CPI", "NOMINAL_GDP")
    if any(not series.get(name) for name in required):
        missing = [name for name in required if not series.get(name)]
        return {"history": [], "current": None, "missingSeries": missing}

    calc = config["calculation"]
    common_months = sorted(set(series["M2"]) & set(series["LF"]) & set(series["L"]) & set(series["CPI"]))
    real = {
        name: {month: series[name][month] / series["CPI"][month] for month in common_months}
        for name in ("M2", "LF", "L")
    }

    real_m2_gaps = one_sided_hp_gaps(
        [(month, real["M2"][month]) for month in common_months],
        calc["hpLambdaMonthly"],
        calc["minMonthlyFilterObservations"],
    )
    real_m2_points = {
        point["period"]: point
        for point in expanding_percentiles(real_m2_gaps, calc["minPercentileHistory"])
    }

    growth_scores = {
        name: _growth_percentiles(real[name], calc["minPercentileHistory"])
        for name in ("M2", "LF", "L")
    }
    breadth_points: dict[str, dict] = {}
    for month in common_months:
        points = [growth_scores[name].get(month) for name in ("M2", "LF", "L")]
        if any(point is None for point in points):
            continue
        breadth_points[month] = {
            "period": month,
            "value": round(sum(float(point["value"]) for point in points) / 3.0, 6),
            "score": round(sum(float(point["score"]) for point in points) / 3.0, 4),
        }

    m2_by_quarter: dict[str, list[float]] = defaultdict(list)
    for month, value in series["M2"].items():
        m2_by_quarter[month_to_quarter(month)].append(value)
    marshall_levels = []
    for quarter in sorted(set(m2_by_quarter) & set(series["NOMINAL_GDP"])):
        monthly_values = m2_by_quarter[quarter]
        if len(monthly_values) != 3:
            continue
        average_m2 = sum(monthly_values) / 3.0
        annualized_gdp = 4.0 * series["NOMINAL_GDP"][quarter]
        marshall_levels.append((quarter, average_m2 / annualized_gdp))
    marshall_gaps = one_sided_hp_gaps(
        marshall_levels,
        calc["hpLambdaQuarterly"],
        calc["minQuarterlyFilterObservations"],
    )
    marshall_points = {
        point["period"]: point
        for point in expanding_percentiles(marshall_gaps, calc["minPercentileHistory"])
    }

    weights = calc["weights"]
    history = []
    for quarter, marshall in marshall_points.items():
        end_month = quarter_end_month(quarter)
        real_m2 = real_m2_points.get(end_month)
        breadth = breadth_points.get(end_month)
        if not real_m2 or not breadth:
            continue
        score = (
            weights["marshallKGap"] * float(marshall["score"])
            + weights["realM2Gap"] * float(real_m2["score"])
            + weights["breadth"] * float(breadth["score"])
        )
        history.append({
            "period": quarter,
            "score": round(score, 2),
            "components": {
                "marshallKGap": marshall,
                "realM2Gap": real_m2,
                "breadth": breadth,
            },
        })
    return {
        "history": history,
        "current": history[-1] if history else None,
        "missingSeries": [],
    }


def canonical_fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def signal_fingerprint(signal: dict) -> str:
    compact = [
        {"period": row["period"], "score": row["score"], "components": row["components"]}
        for row in signal.get("history", [])
    ]
    return canonical_fingerprint(compact)

