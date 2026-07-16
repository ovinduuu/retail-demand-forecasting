import datetime as dt

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("lightgbm")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from retail_demand.serving.app import app  # noqa: E402


def _train_tiny_model(tmp_path) -> str:
    import lightgbm as lgb

    rng = np.random.default_rng(0)
    n = 100
    df = pd.DataFrame(
        {
            "x": rng.normal(size=n),
            "store_id": rng.choice(["CA_1", "CA_2"], size=n),
        }
    )
    df["store_id"] = df["store_id"].astype("category")
    y = df["x"] + df["store_id"].cat.codes.astype(float) * 3

    train_set = lgb.Dataset(df, label=y, categorical_feature=["store_id"])
    model = lgb.train({"objective": "regression", "verbosity": -1}, train_set, num_boost_round=10)

    model_path = tmp_path / "model.txt"
    model.save_model(str(model_path))
    return str(model_path)


def _make_history(days: int = 90) -> pd.DataFrame:
    rng = np.random.default_rng(2)
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


def _train_real_model(tmp_path, history: pd.DataFrame) -> str:
    from retail_demand.models.train import run_training

    model, _, _, _ = run_training(history, valid_days=14)
    model_path = tmp_path / "real_model.txt"
    model.save_model(str(model_path))
    return str(model_path)


def test_health_returns_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_predict_returns_nonnegative_rounded_predictions(tmp_path, monkeypatch):
    model_path = _train_tiny_model(tmp_path)
    monkeypatch.setenv("MODEL_PATH", model_path)

    client = TestClient(app)
    resp = client.post(
        "/predict",
        json={"instances": [{"x": 1.0, "store_id": "CA_1"}, {"x": -5.0, "store_id": "CA_2"}]},
    )

    assert resp.status_code == 200
    predictions = resp.json()["predictions"]
    assert len(predictions) == 2
    assert all(p >= 0 for p in predictions)
    assert all(float(p).is_integer() for p in predictions)


def test_predict_uses_only_the_models_own_feature_columns(tmp_path, monkeypatch):
    model_path = _train_tiny_model(tmp_path)
    monkeypatch.setenv("MODEL_PATH", model_path)

    client = TestClient(app)
    # Extra, unrelated fields in the instance should be ignored rather than error.
    resp = client.post(
        "/predict",
        json={"instances": [{"x": 0.0, "store_id": "CA_1", "unused_field": "ignored"}]},
    )
    assert resp.status_code == 200
    assert len(resp.json()["predictions"]) == 1


def _csv_backed_client(tmp_path, monkeypatch, history: pd.DataFrame) -> TestClient:
    csv_path = tmp_path / "history.csv"
    history.to_csv(csv_path, index=False)
    monkeypatch.setenv("LOCAL_DATA_CSV", str(csv_path))
    monkeypatch.setenv("MODEL_PATH", _train_real_model(tmp_path, history))
    return TestClient(app)


def test_series_lists_distinct_store_item_pairs(tmp_path, monkeypatch):
    history = _make_history()
    client = _csv_backed_client(tmp_path, monkeypatch, history)

    resp = client.get("/series")

    assert resp.status_code == 200
    pairs = {(s["store_id"], s["item_id"]) for s in resp.json()}
    assert pairs == {("CA_1", "FOODS_1_001"), ("CA_1", "FOODS_1_002")}


def test_series_excludes_pairs_with_no_recent_sales(tmp_path, monkeypatch):
    history = _make_history()
    max_date = history["date"].max()
    dormant_rows = pd.DataFrame(
        [
            {"date": date, "store_id": "CA_1", "item_id": "FOODS_1_999", "sales": 0}
            for date in pd.date_range(max_date - pd.Timedelta(days=44), max_date)
        ]
    )
    history = pd.concat([history, dormant_rows], ignore_index=True)
    client = _csv_backed_client(tmp_path, monkeypatch, history)

    resp = client.get("/series")

    assert resp.status_code == 200
    pairs = {(s["store_id"], s["item_id"]) for s in resp.json()}
    assert ("CA_1", "FOODS_1_999") not in pairs
    assert pairs == {("CA_1", "FOODS_1_001"), ("CA_1", "FOODS_1_002")}


def test_history_returns_recent_points_for_known_series(tmp_path, monkeypatch):
    history = _make_history()
    client = _csv_backed_client(tmp_path, monkeypatch, history)

    resp = client.get("/history/CA_1/FOODS_1_001", params={"days": 10})

    assert resp.status_code == 200
    points = resp.json()
    assert len(points) == 10
    assert points[-1]["date"] == history["date"].max().date().isoformat()


def test_history_404s_for_unknown_series(tmp_path, monkeypatch):
    history = _make_history()
    client = _csv_backed_client(tmp_path, monkeypatch, history)

    resp = client.get("/history/UNKNOWN_STORE/UNKNOWN_ITEM")
    assert resp.status_code == 404


def test_forecast_returns_one_nonnegative_point_for_known_series(tmp_path, monkeypatch):
    history = _make_history()
    client = _csv_backed_client(tmp_path, monkeypatch, history)

    resp = client.get("/forecast/CA_1/FOODS_1_001")

    assert resp.status_code == 200
    body = resp.json()
    assert body["predicted_sales"] >= 0
    assert body["date"] == (history["date"].max() + pd.Timedelta(days=1)).date().isoformat()


def _make_predictions(history: pd.DataFrame) -> pd.DataFrame:
    """One prediction per series for each of the last 3 days in `history`,
    offset from the actual by a small fixed amount so accuracy math is
    checkable.
    """
    rows = []
    for (store_id, item_id), series in history.groupby(["store_id", "item_id"]):
        for _, row in series.sort_values("date").tail(3).iterrows():
            rows.append(
                {
                    "date": row["date"],
                    "store_id": store_id,
                    "item_id": item_id,
                    "predicted_sales": row["sales"] + 2,
                }
            )
    return pd.DataFrame(rows)


def _predictions_backed_client(tmp_path, monkeypatch, history: pd.DataFrame) -> TestClient:
    client = _csv_backed_client(tmp_path, monkeypatch, history)
    predictions_path = tmp_path / "predictions.csv"
    _make_predictions(history).to_csv(predictions_path, index=False)
    monkeypatch.setenv("LOCAL_PREDICTIONS_CSV", str(predictions_path))
    return client


def test_accuracy_daily_returns_one_row_per_predicted_date_with_positive_error(
    tmp_path, monkeypatch
):
    history = _make_history()
    client = _predictions_backed_client(tmp_path, monkeypatch, history)

    resp = client.get("/accuracy")

    assert resp.status_code == 200
    days = resp.json()
    assert len(days) == 3
    for day in days:
        assert day["n_predictions"] == 2  # two series in _make_history
        assert day["mae"] == pytest.approx(2.0)
        assert day["rmse"] == pytest.approx(2.0)


def test_series_accuracy_returns_predicted_and_actual_for_one_series(tmp_path, monkeypatch):
    history = _make_history()
    client = _predictions_backed_client(tmp_path, monkeypatch, history)

    resp = client.get("/accuracy/CA_1/FOODS_1_001")

    assert resp.status_code == 200
    points = resp.json()
    assert len(points) == 3
    for point in points:
        assert point["predicted_sales"] == point["actual_sales"] + 2


def test_series_accuracy_empty_for_series_with_no_predictions(tmp_path, monkeypatch):
    history = _make_history()
    client = _predictions_backed_client(tmp_path, monkeypatch, history)

    resp = client.get("/accuracy/UNKNOWN_STORE/UNKNOWN_ITEM")

    assert resp.status_code == 200
    assert resp.json() == []


def test_series_accuracy_excludes_predictions_older_than_the_recent_window(
    tmp_path, monkeypatch
):
    history = _make_history()
    client = _csv_backed_client(tmp_path, monkeypatch, history)
    predictions = _make_predictions(history)
    stale_row = pd.DataFrame(
        [
            {
                "date": history["date"].max() - pd.Timedelta(days=100),
                "store_id": "CA_1",
                "item_id": "FOODS_1_001",
                "predicted_sales": 999,
            }
        ]
    )
    predictions = pd.concat([predictions, stale_row], ignore_index=True)
    predictions_path = tmp_path / "predictions.csv"
    predictions.to_csv(predictions_path, index=False)
    monkeypatch.setenv("LOCAL_PREDICTIONS_CSV", str(predictions_path))

    resp = client.get("/accuracy/CA_1/FOODS_1_001")

    assert resp.status_code == 200
    points = resp.json()
    assert all(p["predicted_sales"] != 999 for p in points)
