"""Feature engineering on top of the project's core sales schema (date,
store_id, item_id, sales), plus whatever optional `fct_sales` columns
(sell_price, snap_flag, event_type_1) happen to be present.

All lag/rolling features are computed from data strictly before the target
date (rolling stats are taken over a series shifted by one day first), so
none of them leak the current day's own sales into its own features.
"""

from __future__ import annotations

import pandas as pd

LAGS = [1, 2, 3, 7, 14, 28]
ROLLING_WINDOWS = [7, 28]

# Raw columns build_features()/feature_columns() can make use of - every
# caller that queries fct_sales for feature-building (pipelines/queries.py,
# serving/app.py, serving/batch_predict.py) must select all of these, or the
# resulting feature set silently comes up short (has_event/snap_flag/
# sell_price missing) and trained-vs-serving feature counts diverge.
RAW_SOURCE_COLUMNS = [
    "date",
    "store_id",
    "item_id",
    "sales",
    "sell_price",
    "snap_flag",
    "event_type_1",
]

ID_COLUMNS = ["store_id", "item_id"]
BASE_NUMERIC_FEATURES = (
    [f"sales_lag_{lag}" for lag in LAGS]
    + [f"sales_roll_mean_{window}" for window in ROLLING_WINDOWS]
    + [f"sales_roll_std_{window}" for window in ROLLING_WINDOWS]
    + ["days_since_last_sale", "dayofweek", "is_weekend", "month"]
)
OPTIONAL_NUMERIC_FEATURES = ["sell_price", "snap_flag", "has_event"]
# event_type_1 only added by feature_columns() if the raw column is present
# (same optional-column pattern as OPTIONAL_NUMERIC_FEATURES) - lets the
# model differentiate event types (Sporting/Cultural/National/Religious)
# instead of collapsing them all into the single has_event binary flag.
CATEGORICAL_FEATURES = ID_COLUMNS + ["event_type_1"]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add lag, rolling, and calendar features to a long-format sales frame.

    Rows without enough history for a given lag/rolling window get NaN in
    that column (the caller is expected to drop or impute before training).
    """
    df = df.sort_values(ID_COLUMNS + ["date"]).reset_index(drop=True)

    for lag in LAGS:
        df[f"sales_lag_{lag}"] = df.groupby(ID_COLUMNS)["sales"].shift(lag)

    shifted = df.groupby(ID_COLUMNS)["sales"].shift(1)
    grouped_shifted = shifted.groupby([df["store_id"], df["item_id"]])
    for window in ROLLING_WINDOWS:
        df[f"sales_roll_mean_{window}"] = grouped_shifted.transform(
            lambda s: s.rolling(window, min_periods=1).mean()
        )
        # Volatility, not just level: two series can share a rolling mean
        # while one is steady and the other is spiky - min_periods=2 since
        # std of a single point is undefined (NaN), same as any other
        # not-enough-history feature (dropped/imputed by the caller).
        df[f"sales_roll_std_{window}"] = grouped_shifted.transform(
            lambda s: s.rolling(window, min_periods=2).std()
        )

    # Days since this series' last nonzero sale, using only data strictly
    # before the current row - the standard feature for intermittent
    # demand (Croston-style), currently the single biggest gap versus pure
    # lag/rolling-mean features for a catalog that's mostly 0s and 1s.
    # Resets to 0 at each sale and at each series' first row (no prior data
    # reads as "a fresh start", not an undefined/unbounded streak).
    had_prior_sale = shifted.fillna(0) > 0
    is_series_start = df.groupby(ID_COLUMNS).cumcount() == 0
    reset_point = had_prior_sale | is_series_start
    df["days_since_last_sale"] = reset_point.groupby(reset_point.cumsum()).cumcount().astype(
        float
    )

    dates = pd.to_datetime(df["date"])
    df["dayofweek"] = dates.dt.dayofweek
    df["is_weekend"] = df["dayofweek"].isin([5, 6]).astype(int)
    df["month"] = dates.dt.month

    if "snap_flag" in df.columns:
        df["snap_flag"] = df["snap_flag"].fillna(0).astype(int)
    if "event_type_1" in df.columns:
        df["has_event"] = df["event_type_1"].notna().astype(int)
        # event_type_1 is null on the ~98% of days with no event - callers
        # (run_training, in particular) drop any row with a null feature
        # value, so leaving real nulls here would silently discard almost
        # the entire dataset once this became a feature column. "none" is
        # an explicit missing-event category instead.
        df["event_type_1"] = df["event_type_1"].fillna("none")

    return df


def feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return (all_feature_columns, categorical_feature_columns) present in `df`."""
    numeric = [c for c in BASE_NUMERIC_FEATURES if c in df.columns]
    numeric += [c for c in OPTIONAL_NUMERIC_FEATURES if c in df.columns]
    categorical = [c for c in CATEGORICAL_FEATURES if c in df.columns]
    return numeric + categorical, categorical
