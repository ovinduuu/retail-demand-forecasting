# Retail Demand Forecasting

End-to-end retail demand forecasting project: data engineering, ML model
training, MLOps, and GCP deployment, built on the
[M5 Forecasting - Accuracy](https://www.kaggle.com/competitions/m5-forecasting-accuracy)
dataset plus a synthetic generator that simulates an ongoing daily feed.

See [`docs/architecture.md`](docs/architecture.md) for the full system diagram
and design rationale, and [`ROADMAP.md`](ROADMAP.md) for what's built vs.
planned.

## Stack

| Layer | Tools |
|---|---|
| Data engineering | GCS, BigQuery, dbt |
| ML | LightGBM, Prophet (baseline), scikit-learn |
| Pipeline / MLOps | Vertex AI Pipelines (KFP v2), Vertex AI Model Registry, Vertex AI Experiments |
| CI/CD | GitHub Actions, Cloud Build |
| Serving | Vertex AI Batch Prediction, FastAPI on Cloud Run (optional) |
| Monitoring | Vertex AI Model Monitoring, BigQuery |
| IaC | Terraform |

## Repo layout

```
src/retail_demand/
  data_engineering/   # download, reshape, load, and synthesize sales data
  models/             # baselines + LightGBM training (Phase 3)
  pipelines/          # Vertex AI Pipeline definitions (Phase 4)
  serving/            # batch prediction + Cloud Run app (Phase 6)
  monitoring/         # drift checks + retrain trigger (Phase 7)
dbt/retail_demand/    # BigQuery transforms: staging -> marts
infra/terraform/       # GCS, BigQuery, service account, Artifact Registry
data/                 # local, gitignored: raw + generated CSVs
notebooks/            # EDA
tests/                # pytest unit tests
```

## Getting started

```bash
uv sync --all-extras
uv run pytest -v
uv run ruff check .
```

To work with real data and cloud resources, follow, in order:

1. [`data/README.md`](data/README.md) — get Kaggle credentials, download M5,
   reshape it, and (optionally) generate a synthetic day of new sales.
2. [`infra/terraform/README.md`](infra/terraform/README.md) — provision a GCS
   bucket + BigQuery datasets + service account in your own GCP project.
3. Load the reshaped CSVs into BigQuery (commands in `data/README.md`), then
   run the dbt project (`dbt/retail_demand/README.md`) to build the marts.

None of steps 2–3 have been run against a real GCP project yet — they need
your own Kaggle account and GCP billing, documented at each step.
