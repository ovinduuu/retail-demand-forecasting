"""FastAPI serving app.

Two roles:

1. Vertex AI's custom-container prediction protocol (GET /health, POST
   /predict with {"instances": [...]} -> {"predictions": [...]}) - the
   `serving_container_image_uri` Phase 4's register_model needs, and the
   image for the optional Cloud Run live-request demo (see
   docs/architecture.md).
2. A small read/forecast API (GET /series, GET /history/{store_id}/{item_id},
   GET /forecast/{store_id}/{item_id}) for the Next.js frontend
   (frontend/) - lists available series, returns recent history, and a
   one-step-ahead forecast, reusing batch_predict.py's prediction logic for
   a single series instead of the whole warehouse.

Data source for (2) is BigQuery's fct_sales mart by default (set
GCP_PROJECT_ID). For local development without GCP credentials, set
LOCAL_DATA_CSV to a long-format CSV (date, store_id, item_id, sales, ...)
instead - see data/README.md's synthetic-feed tooling for how to make one.

Usage:
    MODEL_PATH=artifacts/lightgbm_model.txt GCP_PROJECT_ID=my-project \\
        uv run uvicorn retail_demand.serving.app:app --host 0.0.0.0 --port 8080
"""

import os
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from retail_demand.serving.batch_predict import predict_next_day

DEFAULT_MODEL_PATH = "artifacts/lightgbm_model.txt"
DEFAULT_HISTORY_DAYS = 90
CATEGORICAL_COLUMNS = ["store_id", "item_id"]

_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")

app = FastAPI(title="retail-demand-serving")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allowed_origins == "*" else _allowed_origins.split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_model_cache: dict[str, Any] = {}


def get_model() -> Any:
    """Load (and cache) the LightGBM booster at the path in MODEL_PATH.

    MODEL_PATH may be a gs:// URI (downloaded first via batch_predict.py's
    resolve_model_path) - the fixed path register_model publishes to, see
    docs/monitoring.md. Cached by resolved path rather than as a single
    global, so tests can point MODEL_PATH at a fresh temp model without
    cross-test pollution.
    """
    import lightgbm as lgb

    from retail_demand.serving.batch_predict import resolve_model_path

    model_path = os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH)
    if model_path not in _model_cache:
        _model_cache[model_path] = lgb.Booster(model_file=resolve_model_path(model_path))
    return _model_cache[model_path]


def _bigquery_client_and_table():
    from google.cloud import bigquery

    client = bigquery.Client(project=os.environ["GCP_PROJECT_ID"])
    dataset = os.environ.get("BQ_DATASET_MARTS", "retail_demand_marts")
    table = os.environ.get("BQ_TABLE_SALES", "fct_sales")
    return client, f"{dataset}.{table}"


def _query_series_list() -> pd.DataFrame:
    """Distinct (store_id, item_id) pairs.

    Queried directly with SELECT DISTINCT rather than loading the whole
    fact table into memory and de-duplicating in pandas - fct_sales is tens
    of millions of rows, which previously made this endpoint effectively
    unusable (Cloud Run's default 512Mi + BigQuery's REST fetch path made it
    time out rather than just be slow).

    Reads from LOCAL_DATA_CSV if set (local dev, no GCP needed), otherwise
    from BigQuery's fct_sales mart (GCP_PROJECT_ID must be set).
    """
    local_csv = os.environ.get("LOCAL_DATA_CSV")
    if local_csv:
        history = pd.read_csv(local_csv, parse_dates=["date"])
        return history[["store_id", "item_id"]].drop_duplicates()

    client, table = _bigquery_client_and_table()
    query = f"SELECT DISTINCT store_id, item_id FROM `{table}`"
    return client.query(query).to_dataframe()


def _query_series_history(store_id: str, item_id: str) -> pd.DataFrame:
    """(date, store_id, item_id, sales) rows for exactly one series.

    Filtered server-side (BigQuery WHERE clause) rather than pulling the
    whole fact table and filtering in pandas, for the same reason as
    _query_series_list.
    """
    local_csv = os.environ.get("LOCAL_DATA_CSV")
    if local_csv:
        history = pd.read_csv(local_csv, parse_dates=["date"])
        series = history[(history.store_id == store_id) & (history.item_id == item_id)]
        return series.sort_values("date")

    from google.cloud import bigquery

    client, table = _bigquery_client_and_table()
    query = (
        f"SELECT date, store_id, item_id, sales FROM `{table}` "
        "WHERE store_id = @store_id AND item_id = @item_id ORDER BY date"
    )
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("store_id", "STRING", store_id),
            bigquery.ScalarQueryParameter("item_id", "STRING", item_id),
        ]
    )
    result = client.query(query, job_config=job_config).to_dataframe()
    # BigQuery's client returns DATE columns as plain datetime.date objects,
    # not pandas Timestamps (unlike the LOCAL_DATA_CSV/pd.read_csv path) -
    # normalize here so every downstream consumer (predict_next_day's date
    # arithmetic, the .date().isoformat() calls below) sees the same dtype
    # regardless of which data source this came from.
    result["date"] = pd.to_datetime(result["date"])
    return result


class SeriesInfo(BaseModel):
    store_id: str
    item_id: str


class HistoryPoint(BaseModel):
    date: str
    sales: float


class ForecastPoint(BaseModel):
    date: str
    predicted_sales: float


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


@app.get("/series", response_model=list[SeriesInfo])
def list_series() -> list[SeriesInfo]:
    pairs = _query_series_list()
    return [SeriesInfo(store_id=r.store_id, item_id=r.item_id) for r in pairs.itertuples()]


@app.get("/history/{store_id}/{item_id}", response_model=list[HistoryPoint])
def get_history(
    store_id: str, item_id: str, days: int = DEFAULT_HISTORY_DAYS
) -> list[HistoryPoint]:
    series = _query_series_history(store_id, item_id)
    if series.empty:
        raise HTTPException(status_code=404, detail="Unknown store_id/item_id")

    series = series.tail(days)
    return [
        HistoryPoint(date=row.date.date().isoformat(), sales=float(row.sales))
        for row in series.itertuples()
    ]


@app.get("/forecast/{store_id}/{item_id}", response_model=ForecastPoint)
def get_forecast(store_id: str, item_id: str) -> ForecastPoint:
    series = _query_series_history(store_id, item_id)
    if series.empty:
        raise HTTPException(status_code=404, detail="Unknown store_id/item_id")

    model = get_model()
    prediction = predict_next_day(series, model)
    row = prediction.iloc[0]
    return ForecastPoint(
        date=row.date.date().isoformat(), predicted_sales=float(row.predicted_sales)
    )
