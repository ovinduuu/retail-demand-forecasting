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
- [x] **Phase 2 — EDA & baselines**: naive and seasonal-naive baseline
      models + MAPE/RMSE scoring in `src/retail_demand/models/baseline.py`
      (unit tested); `notebooks/01_eda.ipynb` runs end-to-end on a local
      synthetic sample (seasonality plots + baseline comparison) — swap in a
      real `fct_sales` query once GCP/dbt are set up.
- [x] **Phase 3 — Feature engineering & training**: lag/rolling/calendar
      features (+ price/SNAP/event pass-through) in
      `src/retail_demand/models/features.py`; a LightGBM training CLI
      (`train.py`) with a time-based validation split; evaluation
      (`evaluate.py`) with MAPE, RMSE, and a single-grain sales-weighted
      RMSSE (documented as a simplification of the full 12-level M5 WRMSSE).
      Experiment tracking is a local JSONL run log for now — Vertex AI
      Experiments needs real GCP credentials, deferred to Phase 4.
- [x] **Phase 4 — Pipeline**: Vertex AI Pipeline (KFP v2) —
      `src/retail_demand/pipelines/components.py` (dbt transform, extract
      training data from `fct_sales`, train, conditionally register) wired
      together in `training_pipeline.py`: dbt -> extract -> train ->
      `dsl.If(wrmsse < threshold)` -> register. Compiles locally to a valid
      pipeline spec (unit tested, no GCP credentials needed for that); a
      `Dockerfile` bundles the package + dbt for the components to run in.
      Not yet submitted to a real Vertex AI Pipelines run — needs
      `infra/terraform` applied, the image built + pushed to Artifact
      Registry, and a `serving_container_image_uri` from Phase 6. Wiring
      `train.py`'s run log to Vertex AI Experiments is deferred alongside
      that (needs the same real GCP credentials).
- [x] **Phase 5 — CI/CD**: `cloudbuild.yaml` builds + pushes the pipeline
      image, then runs `src/retail_demand/pipelines/submit_pipeline.py`
      (compiles the pipeline and submits it as a Vertex AI Pipeline Job,
      defaulting to the last 2 years of data if no date range is given);
      `infra/terraform` provisions a `google_cloudbuild_trigger` firing on
      push to `master` (needs the one-time manual GitHub App connection
      documented in `infra/terraform/README.md`). GitHub Actions stays
      scoped to lint/test on every PR — Cloud Build, triggered directly by
      GCP's GitHub connection, owns build+deploy, matching the CI/CB split
      in `docs/architecture.md`.
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
