"""Expanding-window Seoul HaR challenger. Run from any directory."""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, QuantileRegressor
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
data = pd.read_csv(ROOT / "inputs.csv")
features = ["mom12", "CREDIT_GAP_PP", "mortgage_change12", "trade_growth12"]
# Mortgage increases and transaction contractions must occur together.
data["joint_stress"] = (
    data.mortgage_change12.clip(lower=0) * (-data.trade_growth12).clip(lower=0) / 100
)
features_with_stress = features + ["joint_stress"]
valid = data[features_with_stress].notna().all(axis=1)
months = pd.PeriodIndex(data.month, freq="M")
assert months.equals(pd.period_range(months[0], months[-1], freq="M"))
rows = []
for horizon in (6, 12, 36):
    target = 100 * (data.real.shift(-horizon) / data.real - 1)
    for t in range(len(data) - horizon):
        if months[t] < pd.Period("2016-01", freq="M") or not valid.iloc[t]:
            continue
        train = np.flatnonzero(valid & (np.arange(len(data)) + horizon <= t - 3))
        if len(train) < 60:
            continue
        actual = target.iloc[t]
        y = target.iloc[train]
        event = y < 0
        for name, cols in [("기존 금융모형", features), ("동시 스트레스 추가", features_with_stress)]:
            scaler = StandardScaler().fit(data.loc[train, cols])
            X = scaler.transform(data.loc[train, cols])
            now = scaler.transform(data.loc[[t], cols])
            probability = float(event.mean())
            if event.nunique() == 2:
                probability = LogisticRegression(C=.1, max_iter=500).fit(X, event).predict_proba(now)[0, 1]
            q = QuantileRegressor(quantile=.05, alpha=.01, solver="highs").fit(X, y).predict(now)[0]
            error = actual - q
            rows.append(dict(months=horizon, origin=str(months[t]), model=name,
                             brier=(probability - int(actual < 0))**2,
                             pinball05=max(.05 * error, -.95 * error), breach05=error < 0))
scores = pd.DataFrame(rows)
groups = ["months", "model"]
results = []
for label, frame in [("전체", scores), ("2021~2022 기점", scores[scores.origin.between("2021-01","2022-12")])]:
    summary = frame.groupby(groups).agg(n=("brier", "size"), brier=("brier", "mean"),
                                       pinball05=("pinball05", "mean"), breach05=("breach05", "mean")).reset_index()
    summary["period"] = label
    results.append(summary)
pd.concat(results, ignore_index=True).to_csv(ROOT / "challenge.csv", index=False)
print(pd.concat(results, ignore_index=True).round(4).to_string(index=False))
