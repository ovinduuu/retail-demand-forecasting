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
  dataset_id = var.bq_dataset_raw
  project    = var.project_id
  location   = var.bq_location
}

resource "google_bigquery_dataset" "staging" {
  dataset_id = var.bq_dataset_staging
  project    = var.project_id
  location   = var.bq_location
}

resource "google_bigquery_dataset" "marts" {
  dataset_id = var.bq_dataset_marts
  project    = var.project_id
  location   = var.bq_location
}

# --- Artifact Registry for pipeline/serving container images ----------------
resource "google_artifact_registry_repository" "images" {
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

resource "google_project_iam_member" "pipeline_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.pipeline.email}"
}
