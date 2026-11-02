"""AI use case on the gold feature table: forecast a race's final registrations
from what is known at the midpoint of its registration window.

Compares two methods on held-out races (whole events held out, so no leakage):
- naive: double the midpoint count (what people do in a spreadsheet)
- model: gradient boosting on gold features
Reports MAE and MAPE from the real run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import GroupKFold

DB = os.environ.get("DUCKDB_PATH", "data/race_roster.duckdb")
FEATURES = ["capacity", "window_days", "regs_at_quarter", "regs_at_midpoint", "early_bird_regs", "midpoint_fill"]


def run() -> dict:
    df = duckdb.connect(DB, read_only=True).execute("select * from gold.ml_features_race_sellout").df()
    df["early_bird_regs"] = df["early_bird_regs"].clip(upper=df["regs_at_midpoint"])  # only known-by-midpoint
    X, y, groups = df[FEATURES].to_numpy(float), df["final_regs"].to_numpy(float), df["event_id"].to_numpy()
    preds_model, preds_naive = np.zeros_like(y), np.minimum(df["regs_at_midpoint"].to_numpy(float) * 2, df["capacity"])
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
        m = GradientBoostingRegressor(random_state=7, n_estimators=200, max_depth=3).fit(X[tr], y[tr])
        preds_model[te] = np.minimum(m.predict(X[te]), df["capacity"].to_numpy()[te])
    mask = y > 0

    def score(p):
        return dict(mae=round(float(np.mean(np.abs(p - y))), 1),
                    mape_pct=round(float(np.mean(np.abs(p[mask] - y[mask]) / y[mask]) * 100), 1),
                    within_10pct=round(float(np.mean(np.abs(p[mask] - y[mask]) / y[mask] <= 0.10)) * 100, 1))
    res = dict(races=int(len(df)), events=int(df.event_id.nunique()), cv="5-fold grouped by event",
               naive_double_midpoint=score(preds_naive), gradient_boosting=score(preds_model))
    Path("results/forecast_eval.json").write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
