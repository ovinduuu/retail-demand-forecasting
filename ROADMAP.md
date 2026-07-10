# Roadmap

**Status: all 9 phases implemented and merged.** Every phase below is real,
tested code — 54 passing tests, no cloud credentials required to run them.
What's *not* done is deploying any of it to an actual GCP project or
Vercel: that needs a Kaggle account, GCP billing, and a Vercel account that
only you can provide (see "Prerequisites" below). Everywhere a phase says
"written, not applied" or similar, that's the reason.

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
      Registry, and a `serving_container_image_uri` from Phase 6. (Run
      tracking ended up as BigQuery's `model_runs` table, added in Phase 7,
      rather than the originally-planned Vertex AI Experiments — see that
      phase's note below.)
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
- [x] **Phase 6 — Serving**: `src/retail_demand/serving/batch_predict.py` is
      the primary path — one-step-ahead scoring against `fct_sales`, run as
      a scheduled Cloud Run Job (`infra/terraform`'s
      `google_cloud_run_v2_job.batch_predict` + a daily Cloud Scheduler
      trigger). `src/retail_demand/serving/app.py` is a FastAPI service
      (Vertex predict/health protocol) for the optional Cloud Run
      live-request demo, and doubles as the `serving_container_image_uri`
      Phase 4's `register_model` needs — closing a gap found while building
      this phase: Vertex's own model artifact path is versioned/dynamic, so
      `register_model` now also copies each registered model to the fixed
      GCS path `batch_predict.py` reads from. `docker/serving.Dockerfile`
      builds the serving image (separate from the root `Dockerfile`, which
      stays scoped to pipeline/dbt use). Verified locally end-to-end:
      trained a real model, ran the FastAPI server, and hit `/health` and
      `/predict` over actual HTTP. Cloud Run/Scheduler resources are written
      but not applied — same as everything else needing real GCP credentials.
- [x] **Phase 7 — Monitoring**: `src/retail_demand/monitoring/drift_check.py`
      computes Population Stability Index per numeric feature (reference vs.
      current window) and logs to BigQuery's `model_monitoring` table — a
      custom substitute for Vertex AI Model Monitoring, which needs a live
      Endpoint this batch-first project doesn't have (see
      `docs/monitoring.md`). `retrain_trigger.py` reads that plus the latest
      training metrics (now also logged to BigQuery's `model_runs` table by
      the pipeline's `train_model` component — a gap found and fixed while
      building this phase, since `train.py`'s local JSONL log isn't reachable
      from a separate scheduled job) and submits a new pipeline run if either
      regressed. Both run as scheduled Cloud Run Jobs (not Cloud Functions —
      one container-based pattern reused everywhere), added to
      `infra/terraform`. Dashboarding is a documented manual Looker Studio
      step (`docs/monitoring.md`), not something built by this repo.
- [x] **Phase 8 — Polish**: `docs/costs.md` consolidates the per-service cost
      breakdown that used to be scattered across `infra/terraform/README.md`
      (which now just links to it); `README.md` rewritten to describe the
      finished project (accurate stack table — no more claiming Vertex AI
      Batch Prediction/Model Monitoring/Experiments where the real
      implementation is a cheaper custom substitute); a couple of stale
      docs references from earlier phases fixed along the way. No demo
      screenshots: nothing has been deployed to a real GCP project from this
      environment, so there's nothing real to screenshot — the closest thing
      to visual evidence is `notebooks/01_eda.ipynb`, which is committed
      with its actual rendered plots from a real (local, synthetic-data)
      execution.
- [x] **Phase 9 — Frontend**: `frontend/` (Next.js App Router, TypeScript,
      Tailwind) — pick a store/item, see recent sales and the model's
      one-step-ahead forecast on a hand-built SVG chart (no charting
      library). Backend gained three new routes in
      `src/retail_demand/serving/app.py` (`/series`, `/history/{store}/{item}`,
      `/forecast/{store}/{item}`) plus CORS, with a `LOCAL_DATA_CSV` fallback
      so the whole stack is runnable locally without GCP credentials — used
      to verify this phase end-to-end (real backend, real Next.js dev
      server, real HTTP requests, not just unit tests). Frontend deploys to
      Vercel (see `frontend/README.md`), independent of the GCP side.
      Found and fixed three more cross-phase gaps while wiring this up: the
      serving Cloud Run service had no env vars (`GCP_PROJECT_ID`,
      `MODEL_PATH`, `ALLOWED_ORIGINS`) or service account set in Terraform;
      `docker/serving.Dockerfile` was missing the `gcp` extra the new routes
      need; and the root `.gitignore`'s blanket `*.json` rule was silently
      excluding the frontend's `tsconfig.json`/`package-lock.json` (narrowed
      to the specific credential-filename patterns it was actually meant
      to catch).

## Deploying this for real

Everything above is implemented and locally verified wherever that's
possible without cloud credentials. To actually run it against GCP and
Vercel:

1. Get a Kaggle account + API token (`data/README.md`), a GCP project with
   billing enabled, and a Vercel account.
2. Follow `README.md`'s "Getting started" steps 2-4: apply the base
   Terraform infra, load data + run dbt, then build/push both Docker images
   and re-apply Terraform to bring up the Cloud Run services/jobs and
   Cloud Scheduler triggers.
3. Push to `master` (or run `gcloud builds submit --config cloudbuild.yaml`
   manually) to get the first real training pipeline run.
4. Deploy `frontend/` to Vercel pointed at the serving Cloud Run URL from
   step 2 (`frontend/README.md`).

## Prerequisites to unblock real deployment

- Kaggle account + API token (`data/README.md`) — needed to actually pull M5
- GCP project with billing enabled + `gcloud`/`terraform` CLIs installed
  locally — needed to apply `infra/terraform` and run anything against
  BigQuery/Vertex AI
- Vercel account (free tier is fine) — needed to deploy `frontend/`
