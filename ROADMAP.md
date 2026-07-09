# Roadmap

- [x] **Phase 0 — Scaffold**: repo structure, `uv`/`pyproject.toml` dependency
      management, `ruff` lint, GitHub Actions CI, git init.
- [x] **Phase 1 — Data engineering**: M5 download script (`download_m5.py`),
      wide-to-long reshape (`prepare_m5.py`), synthetic daily-feed generator
      (`synthetic_daily_feed.py`, unit tested), BigQuery loader
      (`load_to_bigquery.py`), dbt project (staging + marts:
      `fct_sales`, `dim_item`, `dim_store`, `dim_calendar`), Terraform base
      infra (GCS raw bucket, BigQuery datasets, service account, Artifact
      Registry) — written, not yet applied to a real GCP project.
- [ ] **Phase 2 — EDA & baselines**: `notebooks/01_eda.ipynb`; naive and
      seasonal-naive baseline models in `src/retail_demand/models/baseline.py`.
- [ ] **Phase 3 — Feature engineering & training**: feature build on top of
      `fct_sales` (lags, rolling means, price/promo, calendar features);
      `train.py` (LightGBM) and `evaluate.py` (WRMSSE/MAPE); experiment
      tracking via Vertex AI Experiments.
- [ ] **Phase 4 — Pipeline**: Vertex AI Pipeline (KFP v2) in
      `src/retail_demand/pipelines/training_pipeline.py` wiring
      dbt transform -> feature build -> train -> evaluate -> conditional
      register in Vertex AI Model Registry.
- [ ] **Phase 5 — CI/CD**: extend `.github/workflows` with a Cloud Build
      trigger that runs the Vertex AI pipeline on merge to `main`.
- [ ] **Phase 6 — Serving**: scheduled Vertex AI batch prediction job
      (primary path); optional FastAPI app on Cloud Run for live requests.
- [ ] **Phase 7 — Monitoring**: Vertex AI Model Monitoring (skew/drift),
      metrics logged to BigQuery, Cloud Scheduler + Cloud Function retraining
      trigger, small dashboard.
- [ ] **Phase 8 — Polish**: cost writeup, final README pass, demo screenshots.

## Prerequisites to unblock later phases

- Kaggle account + API token (`data/README.md`) — needed to actually pull M5.
- GCP project with billing enabled + `gcloud`/`terraform` CLIs installed
  locally — needed to apply `infra/terraform` and run anything against
  BigQuery/Vertex AI.
