# Retail Demand Forecasting

End-to-end retail demand forecasting project: data engineering, ML model
training, an orchestrated training pipeline, CI/CD, batch and online
serving, and monitoring — built on the
[M5 Forecasting - Accuracy](https://www.kaggle.com/competitions/m5-forecasting-accuracy)
dataset plus a synthetic generator that simulates an ongoing daily feed.

All 8 planned phases are implemented and merged (see [`ROADMAP.md`](ROADMAP.md)
for the full history). Nothing has been deployed to a real GCP project yet —
that's the one remaining step, and it needs your own Kaggle + GCP credentials
(see "Getting started" below).

See [`docs/architecture.md`](docs/architecture.md) for the system diagram and
design rationale, [`docs/monitoring.md`](docs/monitoring.md) for what's
tracked and how, and [`docs/costs.md`](docs/costs.md) for a full per-service
cost breakdown.

## Stack

| Layer | Tools |
|---|---|
| Data engineering | GCS, BigQuery, dbt |
| ML | LightGBM, scikit-learn, Prophet (optional comparison baseline) |
| Pipeline / MLOps | Vertex AI Pipelines (KFP v2), Vertex AI Model Registry |
| CI/CD | GitHub Actions (lint/test), Cloud Build (image + pipeline submit) |
| Serving | Cloud Run Job (scheduled batch predict, primary path), FastAPI on Cloud Run (optional live-request demo) |
| Monitoring | Custom PSI drift checks + training metrics, both logged to BigQuery; Cloud Run Jobs on Cloud Scheduler |
| IaC | Terraform |

Where this differs from the "obvious" managed-service choice (e.g. no
Vertex AI Batch Prediction, no Vertex AI Model Monitoring, no Cloud
Composer, no Vertex AI Experiments), `docs/architecture.md` and
`docs/monitoring.md` explain why — mostly cost, and mostly because those
products assume a live Endpoint this project doesn't have.

## Repo layout

```
src/retail_demand/
  data_engineering/   # download, reshape, load, and synthesize sales data
  models/             # baselines, feature engineering, LightGBM training, evaluation
  pipelines/          # KFP v2 components + pipeline definition, compile/submit CLI
  serving/            # scheduled batch-predict script + FastAPI app
  monitoring/         # drift checks + retraining trigger
dbt/retail_demand/    # BigQuery transforms: staging -> marts
infra/terraform/      # GCS, BigQuery, Artifact Registry, Cloud Build/Run/Scheduler
docker/               # serving image (root Dockerfile is the pipeline image)
data/                 # local, gitignored: raw + generated CSVs
notebooks/            # EDA (runs standalone on a local synthetic sample)
tests/                # pytest unit tests (50 passing, no cloud creds needed)
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
2. [`infra/terraform/README.md`](infra/terraform/README.md) — provision the
   base GCP infra (GCS, BigQuery, Artifact Registry, service accounts, the
   Cloud Build trigger).
3. Load the reshaped CSVs into BigQuery (commands in `data/README.md`), then
   run the dbt project (`dbt/retail_demand/README.md`) to build the marts.
4. Build and push the two Docker images (root `Dockerfile` for the
   pipeline, `docker/serving.Dockerfile` for serving), then re-apply
   Terraform with `pipeline_image_uri`/`serving_image_uri` set to create the
   Cloud Run services/jobs and their schedulers.

None of steps 2–4 have been run against a real GCP project from this
environment — they need your own Kaggle account and GCP billing, documented
at each step.
