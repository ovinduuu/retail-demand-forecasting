"""FastAPI serving app.

Two roles:

1. Vertex AI's custom-container prediction protocol (GET /health, POST
   /predict with {"instances": [...]} -> {"predictions": [...]}) - the
   `serving_container_image_uri` Phase 4's register_model needs, and the
   image for the optional Cloud Run live-request demo (see
   docs/architecture.md).
2. A small read/forecast API (GET /series, GET /history/{store_id}/{item_id},
   GET /forecast/{store_id}/{item_id}, GET /accuracy,
   GET /accuracy/{store_id}/{item_id}) for the Next.js frontend
   (frontend/) - lists available series, returns recent history, a
   one-step-ahead forecast, and model accuracy (predicted vs. actual, once
   batch_predict.py's predictions have a matching actual - see dbt's
   fct_prediction_accuracy/agg_prediction_accuracy_daily marts).

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
RECENT_ACTIVITY_DAYS = 30
RECENT_ACCURACY_DAYS = 14
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
    """(store_id, item_id) pairs with at least one sale in the last
    RECENT_ACTIVITY_DAYS days.

    Excludes chronically zero-selling series - about 9% of the full M5
    catalog has zero total sales in any given recent 14-day window, which
    otherwise show up in the picker as an item whose chart is flat/empty
    for the entire visible recent range - reads as "data is missing" rather
    than "this item just doesn't sell much," so they're filtered out here
    rather than shown.

    Queried directly (aggregated in BigQuery) rather than loading the whole
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
        recent_start = history["date"].max() - pd.Timedelta(days=RECENT_ACTIVITY_DAYS)
        recent = history[history["date"] > recent_start]
        totals = recent.groupby(["store_id", "item_id"])["sales"].sum()
        return totals[totals > 0].reset_index()[["store_id", "item_id"]]

    client, table = _bigquery_client_and_table()
    query = (
        f"SELECT store_id, item_id FROM `{table}` "
        f"WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL {RECENT_ACTIVITY_DAYS} DAY) "
        "GROUP BY store_id, item_id HAVING SUM(sales) > 0"
    )
    return client.query(query).to_dataframe()


def _query_series_history(store_id: str, item_id: str) -> pd.DataFrame:
    """Full raw feature-source columns (see features.RAW_SOURCE_COLUMNS) for
    exactly one series.

    Must select the same columns queries.build_extract_query() uses for
    training, or predict_next_day's build_features() silently produces fewer
    feature columns than the model was trained on and LightGBM errors out.

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

    from retail_demand.models.features import RAW_SOURCE_COLUMNS

    client, table = _bigquery_client_and_table()
    columns = ", ".join(RAW_SOURCE_COLUMNS)
    query = (
        f"SELECT {columns} FROM `{table}` "
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


def _local_prediction_accuracy() -> pd.DataFrame:
    """Predictions joined to actuals, computed in pandas from LOCAL_DATA_CSV
    + LOCAL_PREDICTIONS_CSV - mirrors dbt's fct_prediction_accuracy model so
    /accuracy* stay unit-testable without BigQuery.
    """
    history = pd.read_csv(os.environ["LOCAL_DATA_CSV"], parse_dates=["date"])
    predictions = pd.read_csv(os.environ["LOCAL_PREDICTIONS_CSV"], parse_dates=["date"])
    merged = predictions.merge(
        history[["date", "store_id", "item_id", "sales"]],
        on=["date", "store_id", "item_id"],
        how="inner",
    ).rename(columns={"sales": "actual_sales"})
    merged["abs_error"] = (merged["predicted_sales"] - merged["actual_sales"]).abs()
    merged["pct_error"] = merged.apply(
        lambda r: r["abs_error"] / r["actual_sales"] if r["actual_sales"] > 0 else None,
        axis=1,
    )
    return merged


def _query_accuracy_daily() -> pd.DataFrame:
    """Daily MAE/MAPE/RMSE, from BigQuery's agg_prediction_accuracy_daily
    mart (or computed locally in dev mode).
    """
    if os.environ.get("LOCAL_PREDICTIONS_CSV"):
        accuracy = _local_prediction_accuracy()
        return (
            accuracy.groupby("date")
            .agg(
                n_predictions=("abs_error", "count"),
                mae=("abs_error", "mean"),
                mape=("pct_error", "mean"),
                rmse=("abs_error", lambda s: float((s**2).mean() ** 0.5)),
            )
            .reset_index()
            .sort_values("date")
        )

    from google.cloud import bigquery

    client = bigquery.Client(project=os.environ["GCP_PROJECT_ID"])
    dataset = os.environ.get("BQ_DATASET_MARTS", "retail_demand_marts")
    query = (
        "SELECT date, n_predictions, mae, mape, rmse "
        f"FROM `{dataset}.agg_prediction_accuracy_daily` ORDER BY date"
    )
    result = client.query(query).to_dataframe()
    result["date"] = pd.to_datetime(result["date"])
    return result


def _query_series_accuracy(store_id: str, item_id: str) -> pd.DataFrame:
    """Predicted-vs-actual points for one series over the last
    RECENT_ACCURACY_DAYS days, from BigQuery's fct_prediction_accuracy mart
    (or computed locally in dev mode) - capped so this stays a "recent
    comparison" endpoint rather than growing unbounded as accuracy history
    accumulates daily.
    """
    if os.environ.get("LOCAL_PREDICTIONS_CSV"):
        accuracy = _local_prediction_accuracy()
        if not accuracy.empty:
            recent_start = accuracy["date"].max() - pd.Timedelta(days=RECENT_ACCURACY_DAYS)
            accuracy = accuracy[accuracy["date"] > recent_start]
        series = accuracy[(accuracy.store_id == store_id) & (accuracy.item_id == item_id)]
        return series.sort_values("date")

    from google.cloud import bigquery

    client = bigquery.Client(project=os.environ["GCP_PROJECT_ID"])
    dataset = os.environ.get("BQ_DATASET_MARTS", "retail_demand_marts")
    query = (
        "SELECT date, predicted_sales, actual_sales "
        f"FROM `{dataset}.fct_prediction_accuracy` "
        "WHERE store_id = @store_id AND item_id = @item_id "
        f"AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL {RECENT_ACCURACY_DAYS} DAY) "
        "ORDER BY date"
    )
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("store_id", "STRING", store_id),
            bigquery.ScalarQueryParameter("item_id", "STRING", item_id),
        ]
    )
    result = client.query(query, job_config=job_config).to_dataframe()
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


class AccuracyDailyPoint(BaseModel):
    date: str
    n_predictions: int
    mae: float
    mape: float | None
    rmse: float


class SeriesAccuracyPoint(BaseModel):
    date: str
    predicted_sales: float
    actual_sales: float


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


@app.get("/accuracy", response_model=list[AccuracyDailyPoint])
def get_accuracy_daily() -> list[AccuracyDailyPoint]:
    daily = _query_accuracy_daily()
    return [
        AccuracyDailyPoint(
            date=row.date.date().isoformat(),
            n_predictions=int(row.n_predictions),
            mae=float(row.mae),
            mape=float(row.mape) if pd.notna(row.mape) else None,
            rmse=float(row.rmse),
        )
        for row in daily.itertuples()
    ]


@app.get("/accuracy/{store_id}/{item_id}", response_model=list[SeriesAccuracyPoint])
def get_series_accuracy(store_id: str, item_id: str) -> list[SeriesAccuracyPoint]:
    series = _query_series_accuracy(store_id, item_id)
    return [
        SeriesAccuracyPoint(
            date=row.date.date().isoformat(),
            predicted_sales=float(row.predicted_sales),
            actual_sales=float(row.actual_sales),
        )
        for row in series.itertuples()
    ]
