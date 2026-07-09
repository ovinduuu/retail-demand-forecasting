variable "project_id" {
  description = "GCP project ID to deploy into."
  type        = string
}

variable "region" {
  description = "Default GCP region."
  type        = string
  default     = "us-central1"
}

variable "bq_location" {
  description = "BigQuery dataset location. Use a multi-region (e.g. US) to stay in the free tier for storage/queries."
  type        = string
  default     = "US"
}

variable "raw_bucket_name" {
  description = "GCS bucket name for raw data landing. Must be globally unique."
  type        = string
}

variable "bq_dataset_raw" {
  type    = string
  default = "retail_demand_raw"
}

variable "bq_dataset_staging" {
  type    = string
  default = "retail_demand_staging"
}

variable "bq_dataset_marts" {
  type    = string
  default = "retail_demand_marts"
}

variable "training_sa_name" {
  description = "Service account used by training/pipeline jobs."
  type        = string
  default     = "retail-demand-pipeline"
}

variable "artifact_repo_name" {
  description = "Artifact Registry Docker repo for pipeline/serving images."
  type        = string
  default     = "retail-demand"
}
