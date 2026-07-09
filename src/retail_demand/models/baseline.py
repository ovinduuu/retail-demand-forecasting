"""Naive and seasonal-naive forecast baselines, plus the metrics used to
score them.

These exist so every later model (LightGBM in Phase 3, etc.) has something
concrete to beat. Both baselines operate on the same long-format schema used
throughout the project: one row per (date, store_id, item_id, sales).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEASON_LENGTH_DEFAULT = 7  # weekly seasonality


def naive_forecast(history: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Repeat each series' last observed value for the next `horizon` days."""
    rows = []
    for (store_id, item_id), series in history.groupby(["store_id", "item_id"]):
        series = series.sort_values("date")
        last_date = series["date"].iloc[-1]
        last_value = series["sales"].iloc[-1]
        for step in range(1, horizon + 1):
            rows.append(
                {
                    "date": last_date + pd.Timedelta(days=step),
                    "store_id": store_id,
                    "item_id": item_id,
                    "sales": last_value,
                }
            )
    return pd.DataFrame(rows, columns=["date", "store_id", "item_id", "sales"])


def seasonal_naive_forecast(
    history: pd.DataFrame, horizon: int, season_length: int = SEASON_LENGTH_DEFAULT
) -> pd.DataFrame:
    """Repeat each series' value from `season_length` days ago, cycling forward."""
    rows = []
    for (store_id, item_id), series in history.groupby(["store_id", "item_id"]):
        series = series.sort_values("date")
        last_date = series["date"].iloc[-1]
        tail = series["sales"].tail(season_length).to_numpy()
        if tail.size == 0:
            continue
        for step in range(1, horizon + 1):
            value = tail[(step - 1) % tail.size]
            rows.append(
                {
                    "date": last_date + pd.Timedelta(days=step),
                    "store_id": store_id,
                    "item_id": item_id,
                    "sales": value,
                }
            )
    return pd.DataFrame(rows, columns=["date", "store_id", "item_id", "sales"])


def mape(y_true: np.ndarray, y_pred: np.ndarray, epsilon: float = 1.0) -> float:
    """Mean absolute percentage error, with an epsilon floor to survive zero actuals."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_true - y_pred) / np.maximum(np.abs(y_true), epsilon)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def score_forecast(actual: pd.DataFrame, forecast: pd.DataFrame) -> dict[str, float]:
    """Join actual vs. forecast on (date, store_id, item_id) and score."""
    merged = actual.merge(
        forecast, on=["date", "store_id", "item_id"], suffixes=("_actual", "_forecast")
    )
    return {
        "mape": mape(merged["sales_actual"], merged["sales_forecast"]),
        "rmse": rmse(merged["sales_actual"], merged["sales_forecast"]),
        "n": len(merged),
    }
