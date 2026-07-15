terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  # Fixed paths shared by the batch-predict, register_model, and
  # retrain_trigger jobs - keeping these in one place avoids the literal
  # gs:// strings drifting out of sync across resources.
  serving_model_gcs_path = "gs://${var.raw_bucket_name}/models/lightgbm_model.txt"
  pipeline_root          = "gs://${var.raw_bucket_name}/pipeline-root"
}

# --- Enable the APIs this project needs -------------------------------------
resource "google_project_service" "apis" {
  for_each = toset([
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudfunctions.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# --- Raw data landing zone ---------------------------------------------------
resource "google_storage_bucket" "raw" {
  depends_on = [google_project_service.apis]

  name                        = var.raw_bucket_name
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = false

  # Keep storage cost near zero for a portfolio project: auto-delete raw
  # objects after 30 days since BigQuery, not GCS, is the source of truth
  # once loaded.
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
}

# --- BigQuery datasets: raw -> staging -> marts ------------------------------
resource "google_bigquery_dataset" "raw" {
  depends_on = [google_project_service.apis]

  dataset_id = var.bq_dataset_raw
  project    = var.project_id
  location   = var.bq_location
}

resource "google_bigquery_dataset" "staging" {
  depends_on = [google_project_service.apis]

  dataset_id = var.bq_dataset_staging
  project    = var.project_id
  location   = var.bq_location
}

resource "google_bigquery_dataset" "marts" {
  depends_on = [google_project_service.apis]

  dataset_id = var.bq_dataset_marts
  project    = var.project_id
  location   = var.bq_location
}

# --- Artifact Registry for pipeline/serving container images ----------------
resource "google_artifact_registry_repository" "images" {
  depends_on = [google_project_service.apis]

  repository_id = var.artifact_repo_name
  project       = var.project_id
  location      = var.region
  format        = "DOCKER"
}

# --- Service account used by Vertex AI Pipelines / training jobs ------------
resource "google_service_account" "pipeline" {
  account_id   = var.training_sa_name
  project      = var.project_id
  display_name = "Retail demand forecasting pipeline runner"
}

resource "google_project_iam_member" "pipeline_bq" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_gcs" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

# storage.objectAdmin covers object reads/writes but not bucket-level
# metadata calls (storage.buckets.get/list) - Vertex AI's PipelineJob.submit()
# does a bucket-existence check before creating the run and 403s without this.
# Only surfaced once retrain_trigger.py actually submitted a pipeline run as
# this service account (previously always run under a user's own credentials).
# legacyBucketReader is bucket-scoped only - not assignable at project level.
resource "google_storage_bucket_iam_member" "pipeline_gcs_bucket_reader" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.pipeline.email}"
}

# Vertex AI's PipelineJob.submit(service_account=...) requires the caller to
# have iam.serviceAccountUser on the SA it's telling Vertex to run steps as -
# including "on itself" when the caller already runs as that SA (this Cloud
# Run Job's identity). Same "only surfaces under automated submission" story
# as the grant above.
resource "google_service_account_iam_member" "pipeline_self_act_as" {
  service_account_id = google_service_account.pipeline.name
  role                = "roles/iam.serviceAccountUser"
  member              = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

resource "google_project_iam_member" "pipeline_logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}

# --- CI/CD: build the pipeline image and submit a training run on push ------
# Requires a one-time manual step before this trigger can be created: install
# the "Google Cloud Build" GitHub App on this repo (Cloud Build console ->
# Triggers -> Connect Repository). See infra/terraform/README.md.
resource "google_cloudbuild_trigger" "training_pipeline" {
  depends_on = [google_project_service.apis]

  project     = var.project_id
  name        = "retail-demand-training-pipeline"
  description = "Build the pipeline image and submit a Vertex AI training run on push to master."
  filename    = "cloudbuild.yaml"

  github {
    owner = var.github_owner
    name  = var.github_repo_name
    push {
      branch = "^master$"
    }
  }

  included_files = [
    "src/retail_demand/**",
    "dbt/**",
    "Dockerfile",
    "cloudbuild.yaml",
  ]

  service_account = google_service_account.pipeline.id
}

# --- Optional: live-request serving API (Cloud Run service) ----------------
# Created only once var.serving_image_uri is set to a real, pushed image -
# the base infra above can be applied without it. Public (allUsers) invoker
# access is granted below so the Vercel frontend can call it directly from
# visitors' browsers without a server-side auth proxy.
resource "google_cloud_run_v2_service" "serving" {
  depends_on = [google_project_service.apis]

  count    = var.serving_image_uri != "" ? 1 : 0
  name     = "retail-demand-serving"
  project  = var.project_id
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.pipeline.email
    scaling {
      min_instance_count = 0 # scale to zero: no idle cost
      max_instance_count = 2
    }
    containers {
      image = var.serving_image_uri
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "BQ_DATASET_MARTS"
        value = var.bq_dataset_marts
      }
      env {
        name  = "MODEL_PATH"
        value = local.serving_model_gcs_path
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.frontend_origin != "" ? var.frontend_origin : "*"
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }
}

# Public read access: the serving API is read-only forecast data with no
# PII, and the Vercel frontend calls it directly from visitors' browsers
# (no server-side proxy that could hold a service-account token instead).
resource "google_cloud_run_v2_service_iam_member" "serving_public" {
  count    = var.serving_image_uri != "" ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.serving[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Daily ingest: scheduled Cloud Run Job + Cloud Scheduler trigger -------
# Created only once var.pipeline_image_uri is set. Earliest in the daily
# chain (03:00 UTC) so drift-check/batch-predict/retrain-trigger all see
# today's data - appends a new synthetic day and refreshes the dbt marts.
resource "google_cloud_run_v2_job" "daily_ingest" {
  depends_on = [google_project_service.apis]

  count    = var.pipeline_image_uri != "" ? 1 : 0
  name     = "retail-demand-daily-ingest"
  project  = var.project_id
  location = var.region

  template {
    template {
      service_account = google_service_account.pipeline.email
      containers {
        image   = var.pipeline_image_uri
        command = ["python", "-m", "retail_demand.data_engineering.daily_ingest"]
        args    = ["--project-id", var.project_id]
        resources {
          limits = {
            # Default 512Mi OOM-killed this job: it loads ~90 days x ~30k
            # series of history into pandas via BigQuery's REST fetch path
            # (no bigquery-storage client), which is heavier than the
            # per-series batch-predict/drift-check queries the default was
            # sized for.
            cpu    = "1"
            memory = "2Gi"
          }
        }
      }
      max_retries = 1
      timeout     = "1800s" # dbt full rebuild of fct_sales included
    }
  }
}

resource "google_service_account" "scheduler" {
  count        = var.pipeline_image_uri != "" ? 1 : 0
  account_id   = "retail-demand-scheduler"
  project      = var.project_id
  display_name = "Invokes the scheduled Cloud Run Jobs on a schedule"
}

resource "google_project_iam_member" "scheduler_run_developer" {
  count   = var.pipeline_image_uri != "" ? 1 : 0
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.scheduler[0].email}"
}

resource "google_cloud_scheduler_job" "daily_ingest_daily" {
  depends_on = [google_project_service.apis]

  count     = var.pipeline_image_uri != "" ? 1 : 0
  name      = "retail-demand-daily-ingest-daily"
  project   = var.project_id
  region    = var.region
  schedule  = "0 3 * * *" # 03:00 UTC daily
  time_zone = "UTC"

  http_target {
    uri = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.daily_ingest[0].name}:run"
    http_method = "POST"
    oauth_token {
      service_account_email = google_service_account.scheduler[0].email
    }
  }
}

# --- Batch prediction: scheduled Cloud Run Job + Cloud Scheduler trigger ---
# Created only once var.pipeline_image_uri is set to a real, pushed image.
resource "google_cloud_run_v2_job" "batch_predict" {
  depends_on = [google_project_service.apis]

  count    = var.pipeline_image_uri != "" ? 1 : 0
  name     = "retail-demand-batch-predict"
  project  = var.project_id
  location = var.region

  template {
    template {
      service_account = google_service_account.pipeline.email
      containers {
        image   = var.pipeline_image_uri
        command = ["python", "-m", "retail_demand.serving.batch_predict"]
        args = [
          "--project-id", var.project_id,
          "--model-path", local.serving_model_gcs_path,
        ]
        resources {
          limits = {
            # Default 512Mi OOM-killed this job the first time it actually
            # ran against real data volume (previously always saw zero rows
            # due to the pre-rebase CURRENT_DATE() staleness bug) - same
            # ~60-days x ~30k-series-via-REST-fetch memory profile as
            # daily_ingest.
            cpu    = "1"
            memory = "2Gi"
          }
        }
      }
      max_retries = 1
      timeout     = "1800s"
    }
  }
}

resource "google_cloud_scheduler_job" "batch_predict_daily" {
  depends_on = [google_project_service.apis]

  count     = var.pipeline_image_uri != "" ? 1 : 0
  name      = "retail-demand-batch-predict-daily"
  project   = var.project_id
  region    = var.region
  schedule  = "0 6 * * *" # 06:00 UTC daily
  time_zone = "UTC"

  http_target {
    uri = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.batch_predict[0].name}:run"
    http_method = "POST"
    oauth_token {
      service_account_email = google_service_account.scheduler[0].email
    }
  }
}

# --- Monitoring: scheduled drift check + retrain trigger --------------------
# Both created only once var.pipeline_image_uri is set. retrain_trigger also
# needs var.serving_image_uri, since a triggered retrain submits a full
# training pipeline run that registers against that serving image.
resource "google_cloud_run_v2_job" "drift_check" {
  depends_on = [google_project_service.apis]

  count    = var.pipeline_image_uri != "" ? 1 : 0
  name     = "retail-demand-drift-check"
  project  = var.project_id
  location = var.region

  template {
    template {
      service_account = google_service_account.pipeline.email
      containers {
        image   = var.pipeline_image_uri
        command = ["python", "-m", "retail_demand.monitoring.drift_check"]
        args    = ["--project-id", var.project_id]
        resources {
          limits = {
            # Same OOM story as batch_predict/daily_ingest, but worse: the
            # reference window alone is 365 days x ~30k series (~11M rows)
            # pulled via BigQuery's REST fetch path.
            cpu    = "1"
            memory = "4Gi"
          }
        }
      }
      max_retries = 1
      timeout     = "1800s"
    }
  }
}

resource "google_cloud_scheduler_job" "drift_check_daily" {
  depends_on = [google_project_service.apis]

  count     = var.pipeline_image_uri != "" ? 1 : 0
  name      = "retail-demand-drift-check-daily"
  project   = var.project_id
  region    = var.region
  schedule  = "0 5 * * *" # 05:00 UTC daily, ahead of batch-predict/retrain-trigger
  time_zone = "UTC"

  http_target {
    uri = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.drift_check[0].name}:run"
    http_method = "POST"
    oauth_token {
      service_account_email = google_service_account.scheduler[0].email
    }
  }
}

resource "google_cloud_run_v2_job" "retrain_trigger" {
  depends_on = [google_project_service.apis]

  count    = var.pipeline_image_uri != "" && var.serving_image_uri != "" ? 1 : 0
  name     = "retail-demand-retrain-trigger"
  project  = var.project_id
  location = var.region

  template {
    template {
      service_account = google_service_account.pipeline.email
      containers {
        image   = var.pipeline_image_uri
        command = ["python", "-m", "retail_demand.monitoring.retrain_trigger"]
        args = [
          "--project-id", var.project_id,
          "--region", var.region,
          "--pipeline-root", local.pipeline_root,
          "--serving-container-image-uri", var.serving_image_uri,
          "--serving-model-gcs-path", local.serving_model_gcs_path,
          "--force", # retrain daily regardless of drift/WRMSSE - see retrain_trigger.py
        ]
        # components.py compiles the pipeline against PIPELINE_IMAGE (defaults
        # to a placeholder if unset); retrain_trigger.py's submission path
        # never actually ran until this env var was added - it was always
        # rejected by check_pipeline_image_is_real()'s placeholder guard.
        env {
          name  = "PIPELINE_IMAGE"
          value = var.pipeline_image_uri
        }
      }
      max_retries = 1
    }
  }
}

resource "google_cloud_scheduler_job" "retrain_trigger_daily" {
  depends_on = [google_project_service.apis]

  count     = var.pipeline_image_uri != "" && var.serving_image_uri != "" ? 1 : 0
  name      = "retail-demand-retrain-trigger-daily"
  project   = var.project_id
  region    = var.region
  schedule  = "30 6 * * *" # 06:30 UTC daily, after drift-check + batch-predict
  time_zone = "UTC"

  http_target {
    uri = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.retrain_trigger[0].name}:run"
    http_method = "POST"
    oauth_token {
      service_account_email = google_service_account.scheduler[0].email
    }
  }
}
