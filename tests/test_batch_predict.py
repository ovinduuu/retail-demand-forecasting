import datetime as dt

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("lightgbm")

from retail_demand.serving.batch_predict import (  # noqa: E402
    build_next_day_frame,
    predict_next_day,
    resolve_model_path,
)


def test_resolve_model_path_passes_through_local_paths():
    assert resolve_model_path("artifacts/lightgbm_model.txt") == "artifacts/lightgbm_model.txt"


def _make_history(days: int = 90) -> pd.DataFrame:
    rng = np.random.default_rng(1)
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


def test_build_next_day_frame_adds_one_stub_row_per_series():
    history = _make_history()
    n_series = history[["store_id", "item_id"]].drop_duplicates().shape[0]

    augmented, next_day = build_next_day_frame(history)

    assert next_day == history["date"].max() + pd.Timedelta(days=1)
    assert len(augmented) == len(history) + n_series
    stub_rows = augmented[augmented["date"] == next_day]
    assert len(stub_rows) == n_series
    assert stub_rows["sales"].isna().all()


def test_predict_next_day_returns_one_nonnegative_row_per_series():
    history = _make_history()
    n_series = history[["store_id", "item_id"]].drop_duplicates().shape[0]

    from retail_demand.models.train import run_training

    model, _, _, _ = run_training(history, valid_days=14)
    predictions = predict_next_day(history, model)

    assert len(predictions) == n_series
    assert (predictions["predicted_sales"] >= 0).all()
    assert (predictions["date"] == history["date"].max() + pd.Timedelta(days=1)).all()
    assert set(predictions.columns) == {"date", "store_id", "item_id", "predicted_sales"}
