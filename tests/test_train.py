import datetime as dt

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("lightgbm")

from retail_demand.models.train import run_training, time_based_split  # noqa: E402


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
