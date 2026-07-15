# Cost notes

Every GCP resource this project provisions, and why it stays cheap. Nothing
here has actually been deployed (see `ROADMAP.md`), so these are informed
estimates based on each service's published free tier and pricing, not
measured spend.

| Service | What it's used for | Why it's cheap |
|---|---|---|
| BigQuery | raw/staging/marts datasets, monitoring tables | 10 GB storage + 1 TB query/month free; a subset-of-M5-sized dataset stays well under that |
| GCS | raw data landing bucket, Vertex pipeline artifacts | 30-day lifecycle rule auto-deletes raw objects (BigQuery is the durable copy); pipeline artifacts are small (a CSV + a LightGBM model file per run) |
| Artifact Registry | pipeline + serving Docker images | storage-only cost for a couple of images, no compute |
| Cloud Build | builds + pushes the pipeline image, submits training runs | 120 free build-minutes/day; one push-triggered build for a project this size fits easily |
| Vertex AI Pipelines | orchestrates dbt transform -> train -> register, now triggered daily (`retrain_trigger.py --force`) rather than only on push | pay-per-run, no idle orchestrator (this is *why* Cloud Composer was ruled out — see `docs/architecture.md`); a run takes a few minutes, so daily instead of occasional adds roughly $1-3/month |
| Vertex AI Model Registry | versioned model metadata | free; you pay for the GCS storage of the artifact itself, which is tiny (a LightGBM model is a few hundred KB - low single-digit MB) |
| Cloud Run (serving service) | live-request demo + the Next.js frontend's backend | `min_instance_count = 0` — scales to zero, billed only per request handled; public (`roles/run.invoker` for `allUsers`) since the frontend calls it from visitors' browsers, but a read-only API with no PII keeps that low-risk |
| Cloud Run Jobs (daily-ingest, batch-predict, drift-check, retrain-trigger) | scheduled data landing, batch scoring, drift check, retrain | billed only for actual run seconds — no standing container between runs. daily-ingest/batch-predict run at 2Gi memory, drift-check at 4Gi (its 365-day reference window is the largest single BigQuery pull in the project) - all still comfortably pay-per-second, not idle cost |
| Cloud Scheduler | triggers the four Cloud Run Jobs daily | free tier covers 3 jobs/account/month; this project uses 4, so the 4th is a fraction of a cent/month past free tier |
| Vercel | hosts the Next.js frontend | free Hobby tier covers a low-traffic personal demo entirely; it's not on GCP at all, so it doesn't touch the free-tier budgets above |

## What's deliberately *not* used, and why

- **Cloud Composer** — an always-on orchestrator would cost real money 24/7
  for something Vertex AI Pipelines already does per-run. See
  `docs/architecture.md`.
- **Pub/Sub + Dataflow** — would be the "correct" way to simulate a
  streaming feed, but real cost/complexity for a project whose actual data
  source (M5) is a frozen historical dataset anyway. Replaced with a
  synthetic daily-feed generator (`data_engineering/synthetic_daily_feed.py`).
- **A standing Vertex AI Endpoint** — the primary serving path is a
  scheduled batch job instead (matches real retail replenishment cadence,
  and avoids paying for an always-on endpoint that would sit idle almost
  all the time).
- **Vertex AI Model Monitoring** — needs a live Endpoint to watch; this
  project doesn't have one. Replaced with custom PSI-based drift checks
  logged to BigQuery (`docs/monitoring.md`).
- **Cloud Functions** — Cloud Run Jobs cover the same "run a scheduled
  script" need using the same container images/tooling already built for
  the pipeline, rather than introducing a second packaging format.

## Rough monthly estimate

For light, personal-portfolio-scale usage with the full daily loop running
(four scheduled Cloud Run Jobs + a daily Vertex AI training run, not
production traffic): likely **$2-5/month**, mostly from the now-daily
Vertex AI training runs and GCS storage of pipeline artifacts/models past
what the always-free tier covers. Still comfortably inexpensive — real cost
only shows up if you materialize much larger BigQuery tables repeatedly or
the public serving API receives meaningful real traffic (it's currently a
low-visibility personal demo, not an indexed/advertised endpoint).
