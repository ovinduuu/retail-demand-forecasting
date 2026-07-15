import datetime as dt

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("lightgbm")

from retail_demand.serving.backfill_predictions import (  # noqa: E402
    backfill_targets,
    run_backfill,
)


def test_backfill_targets_returns_last_n_days_ending_at_latest():
    targets = backfill_targets(dt.date(2026, 7, 14), backfill_days=14)

    assert len(targets) == 14
    assert targets[0] == dt.date(2026, 7, 1)
    assert targets[-1] == dt.date(2026, 7, 14)
    assert targets == sorted(targets)


def _make_history(days: int = 90) -> pd.DataFrame:
    rng = np.random.default_rng(3)
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


def test_run_backfill_predicts_each_target_using_only_prior_history():
    history = _make_history()
    n_series = history[["store_id", "item_id"]].drop_duplicates().shape[0]

    from retail_demand.models.train import run_training

    model, _, _, _ = run_training(history, valid_days=14)

    last_14_dates = sorted(history["date"].dt.date.unique())[-14:]
    predictions = run_backfill(history, last_14_dates, model)

    assert len(predictions) == n_series * 14
    assert set(predictions["date"].dt.date) == set(last_14_dates)
    assert (predictions["predicted_sales"] >= 0).all()


def test_run_backfill_skips_targets_with_no_prior_history():
    history = _make_history()
    too_early = dt.date(2020, 1, 1)  # long before any history exists

    from retail_demand.models.train import run_training

    model, _, _, _ = run_training(history, valid_days=14)
    predictions = run_backfill(history, [too_early], model)

    assert predictions.empty
