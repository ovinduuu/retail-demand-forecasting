import datetime as dt

import pandas as pd

from retail_demand.models.features import build_features, feature_columns


def _make_history(days: int = 40) -> pd.DataFrame:
    start = dt.date(2024, 1, 1)
    rows = []
    for store_id, item_id in [("CA_1", "FOODS_1_001"), ("CA_1", "FOODS_1_002")]:
        for i in range(days):
            rows.append(
                {
                    "date": pd.Timestamp(start + dt.timedelta(days=i)),
                    "store_id": store_id,
                    "item_id": item_id,
                    "sales": float(i % 7),
                }
            )
    return pd.DataFrame(rows)


def test_build_features_adds_expected_columns():
    df = build_features(_make_history())
    for col in [
        "sales_lag_1",
        "sales_lag_2",
        "sales_lag_3",
        "sales_lag_7",
        "sales_lag_14",
        "sales_lag_28",
        "sales_roll_mean_7",
        "sales_roll_mean_28",
        "sales_roll_std_7",
        "sales_roll_std_28",
        "days_since_last_sale",
        "dayofweek",
        "is_weekend",
        "month",
    ]:
        assert col in df.columns


def test_lag_feature_does_not_leak_current_day():
    df = build_features(_make_history())
    one_series = df[(df.store_id == "CA_1") & (df.item_id == "FOODS_1_001")].sort_values("date")
    # sales_lag_7 at row i should equal the raw "sales" value 7 rows earlier.
    shifted_expected = one_series["sales"].shift(7)
    pd.testing.assert_series_equal(
        one_series["sales_lag_7"].reset_index(drop=True),
        shifted_expected.reset_index(drop=True),
        check_names=False,
    )


def test_rolling_mean_excludes_current_day():
    # A constant-then-jump series makes leakage obvious: if today's value
    # leaked into its own rolling mean, the mean at the jump day would move.
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame(
        {
            "date": dates,
            "store_id": ["CA_1"] * 10,
            "item_id": ["FOODS_1_001"] * 10,
            "sales": [5.0] * 9 + [1000.0],
        }
    )
    featured = build_features(df)
    last_row = featured.iloc[-1]
    assert last_row["sales_roll_mean_7"] == 5.0


def test_optional_columns_produce_extra_features():
    df = _make_history(days=10)
    df["sell_price"] = 3.5
    df["snap_flag"] = 1
    # one series (2 series x 10 days, ordered series-then-day): event on the
    # last day of each series.
    df["event_type_1"] = ([None] * 9 + ["National"]) * 2

    featured = build_features(df)
    numeric_and_cat, categorical = feature_columns(featured)

    assert "sell_price" in numeric_and_cat
    assert "snap_flag" in numeric_and_cat
    assert "has_event" in numeric_and_cat
    assert categorical == ["store_id", "item_id", "event_type_1"]
    assert featured["has_event"].sum() == 2  # one event day x 2 series


def test_feature_columns_omits_missing_optional_columns():
    df = build_features(_make_history(days=5))
    numeric_and_cat, categorical = feature_columns(df)
    assert "sell_price" not in numeric_and_cat
    assert "snap_flag" not in numeric_and_cat
    assert categorical == ["store_id", "item_id"]


def test_rolling_std_excludes_current_day():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame(
        {
            "date": dates,
            "store_id": ["CA_1"] * 10,
            "item_id": ["FOODS_1_001"] * 10,
            "sales": [5.0] * 9 + [1000.0],
        }
    )
    featured = build_features(df)
    last_row = featured.iloc[-1]
    assert last_row["sales_roll_std_7"] == 0.0  # the constant 5.0 run, not the jump


def test_days_since_last_sale_resets_on_a_sale_and_at_series_start():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "date": dates,
            "store_id": ["CA_1"] * 5,
            "item_id": ["FOODS_1_001"] * 5,
            "sales": [0.0, 0.0, 3.0, 0.0, 0.0],
        }
    )
    featured = build_features(df).sort_values("date")

    assert featured["days_since_last_sale"].tolist() == [0.0, 1.0, 2.0, 0.0, 1.0]


def test_days_since_last_sale_does_not_cross_series_boundaries():
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    df = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "store_id": ["CA_1"] * 3 + ["CA_2"] * 3,
            "item_id": ["FOODS_1_001"] * 6,
            # CA_1 ends on a long no-sale streak; CA_2 must start fresh at 0,
            # not continue CA_1's streak.
            "sales": [5.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
    )
    featured = build_features(df)
    ca2 = featured[featured.store_id == "CA_2"].sort_values("date")

    assert ca2["days_since_last_sale"].tolist() == [0.0, 1.0, 2.0]
