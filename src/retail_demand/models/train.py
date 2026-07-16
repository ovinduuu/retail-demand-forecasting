"""Train a LightGBM model to forecast daily unit sales.

Reads a long-format CSV (date, store_id, item_id, sales, + optional
sell_price/snap_flag/event_type_1 columns matching `fct_sales`), builds
features (see features.py), holds out the most recent `--valid-days` as a
time-based validation window, trains, evaluates (MAPE/RMSE/WRMSSE), and
writes the model + a run-metrics record.

Experiment tracking: run metrics are appended to a local JSONL file
(`--run-log`) for now. Wiring this to Vertex AI Experiments is a Phase 4 TODO
once the project has real GCP credentials configured (see infra/terraform).

Usage:
    uv run python -m retail_demand.models.train --data data/raw/sales_history.csv
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from retail_demand.models.evaluate import evaluate_predictions
from retail_demand.models.features import ID_COLUMNS, build_features, feature_columns

DEFAULT_VALID_DAYS = 28
DEFAULT_WEIGHT_DAMPENING = "sqrt"

DEFAULT_LGB_PARAMS = {
    "objective": "regression",
    "metric": "rmse",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 20,
    "verbosity": -1,
}


def time_based_split(
    df: pd.DataFrame, valid_days: int = DEFAULT_VALID_DAYS
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hold out the most recent `valid_days` as validation, everything else as train."""
    cutoff = df["date"].max() - pd.Timedelta(days=valid_days)
    train = df[df["date"] <= cutoff]
    valid = df[df["date"] > cutoff]
    return train, valid


def compute_series_weights(
    train_df: pd.DataFrame, dampening: str | None = DEFAULT_WEIGHT_DAMPENING
) -> pd.Series:
    """Per-row training weight from each series' total training-period sales -
    mirrors evaluate.py's WRMSSE weighting, so training loss optimizes
    toward roughly what's actually being measured, instead of uniform
    per-row MSE.

    Dampened (sqrt by default) rather than raw total_sales: an undampened
    weight would let a handful of high-volume series dominate gradient
    updates almost entirely, starving the low-volume long tail that makes
    up most of this catalog - the opposite of what we want. Pass
    dampening=None for the undampened (raw WRMSSE-matching) weight.
    """
    totals = train_df.groupby(ID_COLUMNS)["sales"].transform("sum").astype(float)
    if dampening == "sqrt":
        return totals.pow(0.5)
    if dampening == "log1p":
        return np.log1p(totals)
    if dampening is None:
        return totals
    raise ValueError(f"Unknown dampening: {dampening!r}")


def cast_categoricals(
    train_df: pd.DataFrame, valid_df: pd.DataFrame, categorical_features: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cast categorical feature columns on train/valid to the same dtype + category set.

    Returns new frames the caller should reuse for *both* training and
    prediction — LightGBM requires the categories seen at predict time to
    match training exactly, so this must not be redone independently on
    each side.
    """
    train_df = train_df.copy()
    valid_df = valid_df.copy()
    for col in categorical_features:
        train_df[col] = train_df[col].astype("category")
        valid_df[col] = valid_df[col].astype(
            pd.CategoricalDtype(categories=train_df[col].cat.categories)
        )
    return train_df, valid_df


def train_lightgbm(
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    features: list[str],
    categorical_features: list[str],
    target: str = "sales",
    params: dict | None = None,
    num_boost_round: int = 500,
    sample_weight: pd.Series | None = None,
):
    """Train on `train_df`/`valid_df` as given — callers must already have run
    `cast_categoricals` on them so training and later prediction agree.

    `sample_weight` (see compute_series_weights) only applies to the
    training set, not validation - the tracked eval metric stays plain
    unweighted RMSE, matching how MAPE/RMSE are reported elsewhere."""
    import lightgbm as lgb

    train_set = lgb.Dataset(
        train_df[features],
        label=train_df[target],
        categorical_feature=categorical_features,
        weight=sample_weight.to_numpy() if sample_weight is not None else None,
    )
    valid_set = lgb.Dataset(
        valid_df[features],
        label=valid_df[target],
        categorical_feature=categorical_features,
        reference=train_set,
    )

    model = lgb.train(
        params or DEFAULT_LGB_PARAMS,
        train_set,
        num_boost_round=num_boost_round,
        valid_sets=[valid_set],
        callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)],
    )
    return model


def run_training(
    df: pd.DataFrame,
    valid_days: int = DEFAULT_VALID_DAYS,
    weight_dampening: str | None = None,
) -> tuple[object, dict, pd.DataFrame, list[str]]:
    """Feature-build, split, train, and evaluate. Returns (model, metrics, valid_df, features).

    weight_dampening: None (default) trains with plain unweighted rows;
    "sqrt"/"log1p" weight training rows by compute_series_weights() so the
    training loss leans toward what WRMSSE actually measures. Off by
    default until validated against a specific dataset - see
    compute_series_weights' docstring for why raw (undampened) weighting
    is not offered as a casual default.
    """
    featured = build_features(df)
    features, categorical = feature_columns(featured)

    train_df, valid_df = time_based_split(featured, valid_days)
    train_df = train_df.dropna(subset=features)
    valid_df = valid_df.dropna(subset=features)
    train_df, valid_df = cast_categoricals(train_df, valid_df, categorical)

    sample_weight = (
        compute_series_weights(train_df, dampening=weight_dampening)
        if weight_dampening is not None
        else None
    )
    model = train_lightgbm(
        train_df, valid_df, features, categorical, sample_weight=sample_weight
    )

    preds = model.predict(valid_df[features])
    pred_df = valid_df[["date", "store_id", "item_id"]].assign(
        sales=preds.clip(min=0).round()
    )
    metrics = evaluate_predictions(
        valid_df[["date", "store_id", "item_id", "sales"]],
        pred_df,
        train_df[["date", "store_id", "item_id", "sales"]],
    )
    metrics["best_iteration"] = model.best_iteration
    metrics["n_train_rows"] = len(train_df)
    metrics["n_valid_rows"] = len(valid_df)
    return model, metrics, valid_df, features


def _append_run_log(run_log_path: Path, record: dict) -> None:
    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(run_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="Path to a long-format sales CSV.")
    parser.add_argument("--valid-days", type=int, default=DEFAULT_VALID_DAYS)
    parser.add_argument("--model-out", default="artifacts/lightgbm_model.txt")
    parser.add_argument("--run-log", default="artifacts/runs.jsonl")
    parser.add_argument(
        "--weight-dampening",
        choices=["sqrt", "log1p", "none"],
        default=None,
        help="Weight training rows by each series' total sales (dampened), "
        "matching WRMSSE's weighting. Omit for plain unweighted training.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    df = pd.read_csv(args.data, parse_dates=["date"])
    weight_dampening = None if args.weight_dampening in (None, "none") else args.weight_dampening

    model, metrics, _, features = run_training(df, args.valid_days, weight_dampening)

    model_out = Path(args.model_out)
    model_out.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_out))

    record = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "data": str(args.data),
        "valid_days": args.valid_days,
        "weight_dampening": weight_dampening,
        "features": features,
        "metrics": metrics,
        "model_out": str(model_out),
    }
    _append_run_log(Path(args.run_log), record)

    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
