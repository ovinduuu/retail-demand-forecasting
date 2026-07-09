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
