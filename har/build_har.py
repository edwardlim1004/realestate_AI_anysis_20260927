#!/usr/bin/env python3
"""Independent IMF-inspired House Prices at Risk (HaR) research module.

Outputs NEVER modify risk_summary.json or risk-data.js. Publishing requires a
separate, explicit approval after reviewing out-of-sample results.
"""
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "risk-data" / "risk_raw.csv"
OUT = ROOT / "har" / "results.json"
FEATURES = ("REAL_HPI", "PIR_LTA", "PTR_LTA", "CREDIT_GAP_PP", "DSR_PCT")
HORIZONS = (4, 12)
MIN_TRAIN = 60
MIN_TEST = 12
TAU = 0.05


def load_rows(path=RAW):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_frame(rows, country="KOR"):
    import pandas as pd
    by_key = {}
    for r in rows:
        if r.get("Country") != country or r.get("Frequency") != "Q":
            continue
        if r.get("Indicator") not in FEATURES:
            continue
        period = r.get("Period", "")
        try:
            value = float(r["Value"])
            pd.Period(period.replace("-", ""), freq="Q")
            if math.isfinite(value):
                by_key[(period, r["Indicator"])] = value
        except (ValueError, KeyError):
            continue
    records = {}
    for (period, indicator), value in by_key.items():
        records.setdefault(period, {})[indicator] = value
    if not records:
        raise ValueError("No quarterly observations available")
    frame = pd.DataFrame.from_dict(records, orient="index")
    frame.index = pd.PeriodIndex([p.replace("-", "") for p in frame.index], freq="Q")
    frame = frame.sort_index().asfreq("Q")
    # Housing prices at risk measures the downside tail of REAL price growth.
    frame["momentum_4q"] = 100 * (frame.REAL_HPI / frame.REAL_HPI.shift(4) - 1)
    frame["overvaluation"] = (frame.PIR_LTA + frame.PTR_LTA) / 2 - 100
    # Only measurements already available at forecast origin can be used.
    # Source-vintage / release lag must be checked separately before approval.
    return frame


def design(frame, horizon):
    import numpy as np
    import pandas as pd
    # Minimize degrees of freedom: momentum + affordability + credit gap.
    data = pd.DataFrame(index=frame.index)
    data["momentum_4q"] = frame["momentum_4q"]
    data["overvaluation"] = frame["overvaluation"]
    data["credit_gap"] = frame["CREDIT_GAP_PP"]
    data["target"] = 100 * (frame.REAL_HPI.shift(-horizon) / frame.REAL_HPI - 1)
    data = data.replace([np.inf, -np.inf], np.nan)
    return data


def estimate(train, forecast, tau=TAU):
    import numpy as np
    import statsmodels.api as sm
    cols = ["momentum_4q", "overvaluation", "credit_gap"]
    mean = train[cols].mean()
    std = train[cols].std(ddof=0)
    if (std <= 1e-10).any():
        raise ValueError("Constant or near-constant predictor")
    xx = sm.add_constant((train[cols] - mean) / std, has_constant="add")
    yy = train["target"]
    fit = sm.QuantReg(yy, xx).fit(q=tau, max_iter=10000, p_tol=1e-7)
    new = sm.add_constant((forecast[cols] - mean) / std, has_constant="add")
    result = float(fit.predict(new).iloc[0])
    if not math.isfinite(result):
        raise ValueError("Non-finite forecast")
    return result


def baseline_quantile(training, tau=TAU):
    """Unconditional historical lower-tail benchmark; no fitted covariates."""
    import numpy as np
    return float(np.quantile(training["target"].to_numpy(), tau, method="inverted_cdf"))


def pinball_loss(actual, predicted, tau=TAU):
    delta = actual - predicted
    return tau * delta if delta >= 0 else (1 - tau) * (-delta)


def backtest_diagnostics(rows, tau=TAU):
    n = len(rows)
    if not n:
        return {"n": 0, "breaches": 0, "breach_rate": None, "pinball_loss": None}
    losses = [pinball_loss(r["actual"], r["predicted"], tau) for r in rows]
    breaches = sum(r["breach"] for r in rows)
    return {"n": n, "breaches": breaches,
            "breach_rate": round(breaches / n, 4),
            "pinball_loss": round(sum(losses) / n, 4)}


def run(country="KOR", path=RAW):
    import pandas as pd
    frame = build_frame(load_rows(path), country)
    detail = {}
    for horizon in HORIZONS:
        df = design(frame, horizon)
        valid = df.dropna()
        # Backtesting only origins whose complete forward return is observed.
        # The horizon must be respected: historical target may be used for
        # training only after its future price is known at the origin.
        rows = []
        baseline_rows = []
        for origin in df.index:
            candidate = df.loc[[origin]].dropna(subset=["momentum_4q", "overvaluation", "credit_gap"])
            if candidate.empty:
                continue
            historical = valid.loc[valid.index <= origin - horizon]
            if len(historical) < MIN_TRAIN:
                continue
            predicted = estimate(historical, candidate)
            baseline = baseline_quantile(historical)
            actual = df.loc[origin, "target"]
            if pd.notna(actual):
                rows.append({"period": str(origin), "predicted": round(predicted, 6), "actual": round(float(actual), 6), "breach": bool(actual < predicted)})
                baseline_rows.append({"period": str(origin), "predicted": round(baseline, 6), "actual": round(float(actual), 6), "breach": bool(actual < baseline)})
        # Historical forward-return endpoints in the most recent h quarters
        # are unavailable, so backtest count differs from predicted origins.
        count = len(rows)
        breaches = sum(x["breach"] for x in rows)
        latest = df.dropna(subset=["momentum_4q", "overvaluation", "credit_gap"])
        recent = latest.iloc[[-1]] if not latest.empty else latest
        forecast = None
        if not recent.empty:
            origin = recent.index[-1]
            historical = valid.loc[valid.index <= origin - horizon]
            if len(historical) >= MIN_TRAIN:
                forecast = {"origin": str(origin), "horizon_quarters": horizon, "quantile": TAU,
                            "real_price_change_pct": round(estimate(historical, recent), 4)}
        # Overlapping returns make raw breach counts dependent; no binomial
        # confidence interval should be interpreted as independent coverage.
        detail[str(horizon)] = {
            "forecast": forecast,
            "backtest_n": count,
            "breaches": breaches,
            "breach_rate": round(breaches / count, 4) if count else None,
            "backtest": rows,
            "benchmark": backtest_diagnostics(baseline_rows),
            "model_diagnostics": backtest_diagnostics(rows),
            "calibration_pass": bool(count >= MIN_TEST and abs(breaches / count - TAU) <= 0.05),
            "selection_policy": "Fail closed: require benchmark and model calibration plus publication-vintage and independent signoff. No ad hoc intercept correction.",
            "approved": False,
            "status": "REVIEW_REQUIRED" if count >= MIN_TEST and forecast else "INSUFFICIENT_DATA",
            "validation_gates": {
                "min_60_train_observations": forecast is not None,
                "min_12_out_of_sample_origins": count >= MIN_TEST,
                "release_vintage_no_lookahead": False,
                "calibration_and_benchmark_review": False,
                "independent_signoff": False
            }
        }
    return {
        "schemaVersion": "har.research.v1",
        "generatedAtUTC": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "country": country,
        "input_data_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "model": "IMF-inspired expanding-window linear quantile regression; NOT IMF estimates",
        "source": "risk-data/risk_raw.csv (OECD/BIS official feeds)",
        "unit": "cumulative real house-price change, percent",
        "publication": "RESEARCH_ONLY",
        "composite_eligible": False,
        "warning": "Backtests use revised historical series, not archived real-time vintages. Never insert into the six-indicator composite without point-in-time release-vintage validation, benchmark comparisons, and review.",
        "horizons": detail,
    }


def main():
    result = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    # Avoid daily commits caused only by timestamps or equivalent estimates.
    if OUT.exists():
        previous = json.loads(OUT.read_text(encoding="utf-8"))
        old = {k: v for k, v in previous.items() if k != "generatedAtUTC"}
        new = {k: v for k, v in result.items() if k != "generatedAtUTC"}
        if old == new:
            print("HaR unchanged; research results not committed again.")
            return
    OUT.write_text(serialized, encoding="utf-8")
    print("HaR research results built; composite remains untouched.")


if __name__ == "__main__":
    main()
