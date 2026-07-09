"""FastAPI serving app implementing Vertex AI's custom-container prediction
protocol: GET /health, POST /predict with {"instances": [...]} ->
{"predictions": [...]}.

This is the "optional Cloud Run demo" path from docs/architecture.md - a
live-request example on top of the same LightGBM model artifact. The
project's primary serving path is batch_predict.py, a scheduled script that
queries BigQuery directly instead of going through an HTTP service.

Instances must already be feature rows matching what train.py trained on
(see models/features.py) - this app does not build features itself, mirroring
how a real batch/online split usually separates feature computation
(upstream) from scoring (this service). The exact feature set and column
order needed at predict time is read from the model file itself
(Booster.feature_name()), not hardcoded here.

Usage:
    MODEL_PATH=artifacts/lightgbm_model.txt \\
        uv run uvicorn retail_demand.serving.app:app --host 0.0.0.0 --port 8080
"""

import os
from typing import Any

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel

DEFAULT_MODEL_PATH = "artifacts/lightgbm_model.txt"
CATEGORICAL_COLUMNS = ["store_id", "item_id"]

app = FastAPI(title="retail-demand-serving")

_model_cache: dict[str, Any] = {}


def get_model() -> Any:
    """Load (and cache) the LightGBM booster at the path in MODEL_PATH.

    Cached by resolved path rather than as a single global, so tests can
    point MODEL_PATH at a fresh temp model without cross-test pollution.
    """
    import lightgbm as lgb

    model_path = os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH)
    if model_path not in _model_cache:
        _model_cache[model_path] = lgb.Booster(model_file=model_path)
    return _model_cache[model_path]


class PredictRequest(BaseModel):
    instances: list[dict[str, Any]]


class PredictResponse(BaseModel):
    predictions: list[float]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    df = pd.DataFrame(request.instances)
    for col in CATEGORICAL_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype("category")

    model = get_model()
    feature_names = model.feature_name()
    preds = model.predict(df[feature_names])
    predictions = [max(0.0, round(float(p))) for p in preds]
    return PredictResponse(predictions=predictions)
