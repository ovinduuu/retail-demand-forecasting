"""Evaluation for demand forecasts: MAPE/RMSE (reused from baseline.py) plus
RMSSE / weighted RMSSE.

Note on scope: this computes RMSSE at the single (store_id, item_id) grain
only — the finest level of the real M5 hierarchy. The actual competition
metric (WRMSSE) averages RMSSE across all 12 aggregation levels (total,
per-category, per-store, etc.) with dollar-sales-based weights; reproducing
that full hierarchy is out of scope for this project. Where the roadmap/docs
say "WRMSSE", they mean this single-level, sales-weighted approximation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from retail_demand.models.baseline import mape, rmse

ID_COLUMNS = ["store_id", "item_id"]


def _naive_step_scale(train_sales: np.ndarray) -> float:
    """RMSSE's denominator: MSE of the one-step-ahead naive forecast on training data."""
    diffs = np.diff(train_sales)
    if diffs.size == 0:
        return 1.0
    scale = float(np.mean(diffs**2))
    return scale if scale > 0 else 1.0


def rmsse_per_series(
    actual: pd.DataFrame, forecast: pd.DataFrame, train: pd.DataFrame
) -> pd.DataFrame:
    """RMSSE for each (store_id, item_id) series, plus its total training-period sales
    (used as the weight in `weighted_rmsse`)."""
    merged = actual.merge(
        forecast, on=["date", *ID_COLUMNS], suffixes=("_actual", "_forecast")
    )
    rows = []
    for (store_id, item_id), group in merged.groupby(ID_COLUMNS):
        train_series = (
            train[(train.store_id == store_id) & (train.item_id == item_id)]
            .sort_values("date")["sales"]
            .to_numpy(dtype=float)
        )
        scale = _naive_step_scale(train_series)
        mse = float(np.mean((group["sales_actual"] - group["sales_forecast"]) ** 2))
        rows.append(
            {
                "store_id": store_id,
                "item_id": item_id,
                "rmsse": float(np.sqrt(mse / scale)),
                "total_sales": float(train_series.sum()),
            }
        )
    return pd.DataFrame(rows, columns=["store_id", "item_id", "rmsse", "total_sales"])


def weighted_rmsse(per_series: pd.DataFrame, weight_col: str = "total_sales") -> float:
    """Sales-weighted mean RMSSE (falls back to a plain mean if weights are all zero)."""
    weights = per_series[weight_col]
    if weights.sum() == 0:
        return float(per_series["rmsse"].mean())
    return float((per_series["rmsse"] * weights).sum() / weights.sum())


def evaluate_predictions(
    actual: pd.DataFrame, forecast: pd.DataFrame, train: pd.DataFrame
) -> dict:
    """MAPE, RMSE, and weighted RMSSE for a forecast against actuals, scaled using `train`."""
    merged = actual.merge(
        forecast, on=["date", *ID_COLUMNS], suffixes=("_actual", "_forecast")
    )
    per_series = rmsse_per_series(actual, forecast, train)
    return {
        "mape": mape(merged["sales_actual"], merged["sales_forecast"]),
        "rmse": rmse(merged["sales_actual"], merged["sales_forecast"]),
        "wrmsse": weighted_rmsse(per_series),
        "n": len(merged),
        "n_series": len(per_series),
    }
