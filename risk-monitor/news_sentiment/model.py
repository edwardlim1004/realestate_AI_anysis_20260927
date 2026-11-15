"""Isolated, retrospective evaluation of Korean NSI for Seoul apartment-price risk.

No score from this module is eligible for the operational composite.
All monthly features use month t-1 (or earlier) to forecast changes AFTER t-1.
Publication-time availability and true historical vintages require separate evidence.
"""
from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

HORIZONS = (1, 3, 6)
BASE_FIELDS = ("price_momentum_lag1", "price_momentum_lag2", "real_rate_lag5", "excess_liquidity_lag10", "kospi_return_lag1")
NSI_FIELDS = ("new_nsi", "nsi_change")
MIN_TRAIN = 60
MIN_OOS = 24


def parse_month(raw: str) -> date:
    match = re.fullmatch(r"(\d{4})[-/]?(\d{2})", str(raw).strip())
    if not match:
        raise ValueError(f"Invalid month: {raw!r}; expected YYYY-MM")
    return date(int(match.group(1)), int(match.group(2)), 1)


def month_add(month: date, step: int) -> date:
    count = month.year * 12 + month.month - 1 + step
    return date(count // 12, count % 12 + 1, 1)


def read_monthly_csv(path: Path, columns: tuple[str, ...]) -> dict[date, dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"month", *columns}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"{path}: required columns {sorted(required)}")
        results = {}
        for row in reader:
            month = parse_month(row["month"])
            if month in results:
                raise ValueError(f"{path}: duplicate period {month}")
            values = {}
            for col in columns:
                raw = (row[col] or "").strip()
                if not raw:
                    raise ValueError(f"{path}: missing {col} at {month}")
                value = float(raw)
                if not math.isfinite(value):
                    raise ValueError(f"{path}: non-finite {col} at {month}")
                values[col] = value
            # Optional Expected NSI remains a separate candidate; never silently
            # substitute it for the headline NSI or fill it forward.
            raw_expected = (row.get("expected_nsi") or "").strip()
            if raw_expected:
                expected = float(raw_expected)
                if not math.isfinite(expected):
                    raise ValueError(f"{path}: invalid expected_nsi at {month}")
                values["expected_nsi"] = expected
            results[month] = values
    return results


@dataclass(frozen=True)
class Observation:
    origin: date
    target_end: date
    baseline: tuple[float, ...]
    augmented: tuple[float, ...]
    target: float


def build_observations(
    price: dict[date, dict], nsi: dict[date, dict], control: dict[date, dict],
    horizon: int, use_expected: bool = False,
) -> list[Observation]:
    if horizon not in HORIZONS:
        raise ValueError("Unsupported horizon")
    if not price:
        return []
    start = min(price)
    end = max(price)
    rows = []
    month = month_add(start, 11)
    while month_add(month, horizon - 1) <= end:
        prev, before = month_add(month, -1), month_add(month, -2)
        target_end = month_add(month, horizon - 1)
        older = month_add(month, -3)
        rate_lag = month_add(month, -5)
        liquidity_lag = month_add(month, -10)
        if not all(key in price for key in (older, before, prev, target_end)):
            month = month_add(month, 1)
            continue
        if not all(key in control for key in (prev, rate_lag, liquidity_lag)) or prev not in nsi or before not in nsi:
            month = month_add(month, 1)
            continue
        if use_expected and "expected_nsi" not in nsi[prev]:
            month = month_add(month, 1)
            continue
        p_older = price[older]["price_index"]
        p0 = price[before]["price_index"]
        p1 = price[prev]["price_index"]
        p_end = price[target_end]["price_index"]
        if min(p_older, p0, p1, p_end) <= 0:
            raise ValueError("Price indices must be positive")
        base = (
            math.log(p1 / p0),
            math.log(p0 / p_older),
            control[rate_lag]["real_rate"],
            control[liquidity_lag]["excess_liquidity"],
            control[prev]["kospi_return"],
        )
        more = (nsi[prev]["new_nsi"], nsi[prev]["new_nsi"] - nsi[before]["new_nsi"])
        if use_expected:
            more += (nsi[prev]["expected_nsi"],)
        rows.append(Observation(month, target_end, base, base + more, math.log(p_end / p1)))
        month = month_add(month, 1)
    return rows


def ridge_predict(x: np.ndarray, y: np.ndarray, point: np.ndarray, alpha: float = 10.0) -> float:
    """Training-only scaling; intercept is not penalized."""
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-12] = 1.0
    xx = (x - mean) / scale
    xp = (point - mean) / scale
    design = np.column_stack((np.ones(len(xx)), xx))
    penalty = np.diag([0.0] + [alpha] * xx.shape[1])
    coef = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return float(np.r_[1.0, xp] @ coef)


def _metrics(actual: np.ndarray, forecast: np.ndarray) -> dict:
    negative = actual < 0
    warnings = forecast < 0
    tp = int(np.sum(negative & warnings))
    fp = int(np.sum(~negative & warnings))
    fn = int(np.sum(negative & ~warnings))
    tn = int(np.sum(~negative & ~warnings))
    return {
        "rmse": round(float(np.sqrt(np.mean((actual - forecast) ** 2))), 8),
        "mae": round(float(np.mean(np.abs(actual - forecast))), 8),
        "directionalAccuracy": round(float(np.mean(np.sign(actual) == np.sign(forecast))), 4),
        "downturnRecall": round(tp / (tp + fn), 4) if tp + fn else None,
        "falsePositiveRate": round(fp / (fp + tn), 4) if fp + tn else None,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def _dm_pvalue(loss_improvement: np.ndarray, horizon: int) -> float | None:
    """Two-sided normal approximation; HAC bandwidth=h-1 for overlapping returns."""
    n = len(loss_improvement)
    if n < 12:
        return None
    centered = loss_improvement - loss_improvement.mean()
    long_var = float(centered @ centered) / n
    for lag in range(1, min(horizon, n)):
        gamma = float(centered[lag:] @ centered[:-lag]) / n
        long_var += 2 * (1 - lag / horizon) * gamma
    if long_var <= 1e-16:
        return None
    z = float(loss_improvement.mean()) / math.sqrt(long_var / n)
    return round(math.erfc(abs(z) / math.sqrt(2)), 6)


def evaluate(observations: list[Observation], horizon: int, min_train: int = MIN_TRAIN) -> dict:
    actual, base_predictions, nsi_predictions, forecast_months = [], [], [], []
    # A label may train the model only if its entire horizon ends before
    # the forecasting origin; no target from the future is used in training.
    for i, current in enumerate(observations):
        training = [r for r in observations[:i] if r.target_end < current.origin]
        if len(training) < min_train:
            continue
        y = np.array([r.target for r in training], dtype=float)
        xb = np.array([r.baseline for r in training], dtype=float)
        xa = np.array([r.augmented for r in training], dtype=float)
        actual.append(current.target)
        base_predictions.append(ridge_predict(xb, y, np.array(current.baseline)))
        nsi_predictions.append(ridge_predict(xa, y, np.array(current.augmented)))
        forecast_months.append(current.origin.strftime("%Y-%m"))
    if len(actual) < MIN_OOS:
        return {
            "status": "INSUFFICIENT_OOS",
            "forecastCount": len(actual),
            "minRequired": MIN_OOS,
            "months": [forecast_months[0], forecast_months[-1]] if forecast_months else [],
        }
    y = np.array(actual)
    b = np.array(base_predictions)
    n = np.array(nsi_predictions)
    baseline = _metrics(y, b)
    augmented = _metrics(y, n)
    reduction = (1 - augmented["rmse"] / baseline["rmse"]) * 100 if baseline["rmse"] else None
    improvements = (y - b) ** 2 - (y - n) ** 2
    p = _dm_pvalue(improvements, horizon)
    baseline_fpr, nsi_fpr = baseline["falsePositiveRate"], augmented["falsePositiveRate"]
    gates = {
        "rmseReductionAtLeast3Pct": reduction is not None and reduction >= 3,
        "hacPValueBelow005": p is not None and p < 0.05,
        "noFprDeteriorationOver5pp": (
            baseline_fpr is not None and nsi_fpr is not None and nsi_fpr - baseline_fpr <= 0.05
        ),
        "atLeast12Downturns": int(np.sum(y < 0)) >= 12,
    }
    return {
        "status": "RETROSPECTIVE_ONLY",
        "forecastCount": len(y),
        "forecastMonths": [forecast_months[0], forecast_months[-1]],
        "actualDownturns": int(np.sum(y < 0)),
        "baseline": baseline, "withNSI": augmented,
        "rmseReductionPct": round(reduction, 3) if reduction is not None else None,
        "dieBoldMarianoHacApproxPValue": p,
        "researchGates": gates,
        "researchGatesAllPass": all(gates.values()),
        "readyForProduction": False,
    }


def run(prices: Path, nsi_path: Path, controls: Path) -> dict:
    common = {
        "moduleId": "KOR_NEW_NSI_SEOUL_HOUSING",
        "schemaVersion": "1.0",
        "mode": "SHADOW_VALIDATION",
        "publicScore": None,
        "compositeEligible": False,
        "realTimeForecastVerified": False,
        "asOfEvidence": "RETROSPECTIVE_NO_POINT_IN_TIME_VINTAGES",
        "model": "expanding-window ridge; lagged monthly predictors; embargo by prediction horizon",
    }
    missing = [str(path) for path in (prices, nsi_path, controls) if not path.is_file()]
    if missing:
        return {**common, "mode": "SHADOW_WAITING_DATA", "missingInputs": missing, "horizons": {}}
    try:
        p = read_monthly_csv(prices, ("price_index",))
        n = read_monthly_csv(nsi_path, ("new_nsi",))
        c = read_monthly_csv(controls, ("real_rate", "excess_liquidity", "kospi_return"))
        if any(not x for x in (p, n, c)):
            raise ValueError("One or more CSV inputs are empty")
        # Never silently use mixed or unidentified index vintages.
        expected_available = all("expected_nsi" in x for x in n.values())
        results = {
            str(h): evaluate(build_observations(p, n, c, h), h)
            for h in HORIZONS
        }
        if expected_available:
            results_expected = {
                str(h): evaluate(build_observations(p, n, c, h, use_expected=True), h)
                for h in HORIZONS
            }
        else:
            results_expected = {"status": "NOT_PROVIDED"}
        return {
            **common, "horizons": results, "withExpectedNSI": results_expected,
            "inputCounts": {"price": len(p), "nsi": len(n), "controls": len(c)},
            "coverage": {
                "price": [min(p).isoformat(), max(p).isoformat()],
                "nsi": [min(n).isoformat(), max(n).isoformat()],
                "controls": [min(c).isoformat(), max(c).isoformat()],
            },
            "limitations": [
                "The series published in 2026 may be historically backfilled; pre-2026 backtests are NOT real-time vintage tests",
                "Official release dates, historical revisions and simultaneous availability are not verified",
                "The 2021-2026 transaction-mix-dependent district series is NOT accepted as a substitute for a Seoul apartment price index",
                "This result cannot change HaR eligibility or any operational composite score",
            ],
        }
    except (ValueError, OSError) as exc:
        return {**common, "mode": "SHADOW_INVALID_INPUT", "error": str(exc), "horizons": {}}


def write_result(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
