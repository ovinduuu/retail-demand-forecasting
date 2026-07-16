import datetime as dt

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("lightgbm")

from retail_demand.models.train import (  # noqa: E402
    compute_series_weights,
    run_training,
    time_based_split,
)


def _make_history(days: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    start = dt.date(2024, 1, 1)
    weekday_multiplier = np.array([1.0, 0.9, 0.9, 1.0, 1.1, 1.4, 1.3])
    rows = []
    for store_id, item_id in [("CA_1", "FOODS_1_001"), ("CA_1", "FOODS_1_002")]:
        base = rng.uniform(8, 20)
        for i in range(days):
            date = start + dt.timedelta(days=i)
            seasonal = base * weekday_multiplier[date.weekday()]
            noise = rng.normal(loc=1.0, scale=0.1)
            sales = max(0, round(seasonal * noise))
            rows.append(
                {
                    "date": pd.Timestamp(date),
                    "store_id": store_id,
                    "item_id": item_id,
                    "sales": sales,
                }
            )
    return pd.DataFrame(rows)


def test_time_based_split_holds_out_recent_days():
    history = _make_history()
    train, valid = time_based_split(history, valid_days=14)

    assert train["date"].max() == valid["date"].min() - pd.Timedelta(days=1)
    assert (valid["date"] > train["date"].max()).all()


def test_run_training_produces_model_and_metrics():
    history = _make_history()
    model, metrics, valid_df, features = run_training(history, valid_days=14)

    assert model.num_trees() > 0
    assert set(["mape", "rmse", "wrmsse", "n", "n_series"]).issubset(metrics)
    assert metrics["n"] > 0
    assert len(features) > 0
    assert not valid_df.empty


def test_run_training_accepts_weight_dampening():
    history = _make_history()
    model, metrics, _, _ = run_training(history, valid_days=14, weight_dampening="sqrt")

    assert model.num_trees() > 0
    assert metrics["n"] > 0


def test_compute_series_weights_orders_by_total_sales():
    df = pd.DataFrame(
        {
            "store_id": ["CA_1"] * 3 + ["CA_2"] * 3,
            "item_id": ["FOODS_1_001"] * 3 + ["FOODS_1_002"] * 3,
            "sales": [10, 10, 10, 1, 1, 1],  # CA_1 series sells 10x as much
        }
    )
    weights = compute_series_weights(df, dampening=None)
    sqrt_weights = compute_series_weights(df, dampening="sqrt")

    assert (weights[df.store_id == "CA_1"] == 30).all()
    assert (weights[df.store_id == "CA_2"] == 3).all()
    # dampening narrows the gap between high- and low-volume series without
    # reversing their order.
    raw_ratio = 30 / 3
    ca1_sqrt = sqrt_weights[df.store_id == "CA_1"].iloc[0]
    ca2_sqrt = sqrt_weights[df.store_id == "CA_2"].iloc[0]
    assert 1 < ca1_sqrt / ca2_sqrt < raw_ratio
