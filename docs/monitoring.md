# Monitoring

## Why not Vertex AI Model Monitoring

Vertex's managed Model Monitoring product watches request/response logs on
a live **Endpoint**. This project's primary serving path is a batch job
(`src/retail_demand/serving/batch_predict.py`, see
[architecture.md](architecture.md)) with no standing Endpoint, so that
product doesn't have anything to attach to. `drift_check.py` is the
substitute: a scheduled job that computes the same kind of signal (feature
distribution drift) directly against BigQuery, using the Population
Stability Index (PSI) — a standard, well-known metric, not something
specific to Vertex.

## What gets logged, and where

Two tables in the `retail_demand_marts` BigQuery dataset, both created
automatically on first write (via pandas-DataFrame schema inference — no
Terraform-managed table resource needed):

- **`model_monitoring`** — one row per (feature, drift-check run): `feature`,
  `psi`, `drifted` (`psi > 0.2`, the standard PSI threshold), `checked_at`.
  Written by `drift_check.py`.
- **`model_runs`** — one row per training run: `trained_at`, `wrmsse`,
  `mape`, `rmse`, `n_train_rows`, `n_valid_rows`. Written by the training
  pipeline's `train_model` component (`src/retail_demand/pipelines/components.py`)
  — this is the same run separately logged locally by `train.py` to a JSONL
  file; the BigQuery copy is what a scheduled job elsewhere in the project
  can actually read.

## Retraining trigger

`retail_demand.monitoring.retrain_trigger` reads the latest row per feature
from `model_monitoring` and the most recent row from `model_runs`, decides
whether to retrain (`retrain_trigger.should_retrain`: drift detected in at
least one feature, OR the latest WRMSSE regressed past a threshold), and if
so, compiles and submits a new training pipeline run using the same
`pipelines/submit_pipeline.py` logic Cloud Build already calls after a push
to `master`.

Scheduling (`infra/terraform`, all UTC): `drift-check` at 05:00,
`batch-predict` at 06:00, `retrain-trigger` at 06:30 — drift gets checked and
predictions refreshed before the retrain decision is made off that same
day's data.

## Dashboard

No dashboard is built by this repo — Looker Studio dashboards are built
through its console UI, not code, so this is a manual step once you have
real data in `model_monitoring`/`model_runs`:

1. Looker Studio -> Create -> Report -> BigQuery -> your project ->
   `retail_demand_marts` -> `model_monitoring` (and a second data source for
   `model_runs`).
2. A PSI-over-time line chart per feature (from `model_monitoring`) and a
   WRMSSE-over-time line chart (from `model_runs`) cover the two signals
   `retrain_trigger.py` actually acts on.
