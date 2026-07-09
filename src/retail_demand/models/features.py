"""Feature engineering on top of the project's core sales schema (date,
store_id, item_id, sales), plus whatever optional `fct_sales` columns
(sell_price, snap_flag, event_type_1) happen to be present.

All lag/rolling features are computed from data strictly before the target
date (rolling stats are taken over a series shifted by one day first), so
none of them leak the current day's own sales into its own features.
"""

from __future__ import annotations

import pandas as pd

LAGS = [7, 14, 28]
ROLLING_WINDOWS = [7, 28]

ID_COLUMNS = ["store_id", "item_id"]
BASE_NUMERIC_FEATURES = (
    [f"sales_lag_{lag}" for lag in LAGS]
    + [f"sales_roll_mean_{window}" for window in ROLLING_WINDOWS]
    + ["dayofweek", "is_weekend", "month"]
)
OPTIONAL_NUMERIC_FEATURES = ["sell_price", "snap_flag", "has_event"]
CATEGORICAL_FEATURES = ID_COLUMNS


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add lag, rolling, and calendar features to a long-format sales frame.

    Rows without enough history for a given lag/rolling window get NaN in
    that column (the caller is expected to drop or impute before training).
    """
    df = df.sort_values(ID_COLUMNS + ["date"]).reset_index(drop=True)

    for lag in LAGS:
        df[f"sales_lag_{lag}"] = df.groupby(ID_COLUMNS)["sales"].shift(lag)

    shifted = df.groupby(ID_COLUMNS)["sales"].shift(1)
    for window in ROLLING_WINDOWS:
        df[f"sales_roll_mean_{window}"] = shifted.groupby(
            [df["store_id"], df["item_id"]]
        ).transform(lambda s: s.rolling(window, min_periods=1).mean())

    dates = pd.to_datetime(df["date"])
    df["dayofweek"] = dates.dt.dayofweek
    df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)
    df["month"] = dates.dt.month

    if "snap_flag" in df.columns:
        df["snap_flag"] = df["snap_flag"].fillna(0).astype(int)
    if "event_type_1" in df.columns:
        df["has_event"] = df["event_type_1"].notna().astype(int)

    return df


def feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return (all_feature_columns, categorical_feature_columns) present in `df`."""
    numeric = [c for c in BASE_NUMERIC_FEATURES if c in df.columns]
    numeric += [c for c in OPTIONAL_NUMERIC_FEATURES if c in df.columns]
    categorical = [c for c in CATEGORICAL_FEATURES if c in df.columns]
    return numeric + categorical, categorical
