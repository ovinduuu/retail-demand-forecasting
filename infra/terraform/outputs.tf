output "raw_bucket_name" {
  value = google_storage_bucket.raw.name
}

output "bq_dataset_raw" {
  value = google_bigquery_dataset.raw.dataset_id
}

output "bq_dataset_staging" {
  value = google_bigquery_dataset.staging.dataset_id
}

output "bq_dataset_marts" {
  value = google_bigquery_dataset.marts.dataset_id
}

output "pipeline_service_account_email" {
  value = google_service_account.pipeline.email
}

output "artifact_registry_repo" {
  value = google_artifact_registry_repository.images.name
}

output "cloudbuild_trigger_id" {
  value = google_cloudbuild_trigger.training_pipeline.trigger_id
}
