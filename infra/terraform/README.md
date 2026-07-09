# Terraform — base GCP infra

Provisions the minimum shared infra: raw GCS bucket, BigQuery datasets
(raw/staging/marts), an Artifact Registry Docker repo, and a service account
for pipeline/training jobs. Vertex AI Pipeline resources, Cloud Run services,
and the Cloud Scheduler retraining trigger are added in later phases (once
those components exist) rather than provisioned up front.

**Not yet applied** — this requires your own GCP project and billing. Nothing
in this repo has touched real cloud resources.

## Prerequisites

1. A GCP project with billing enabled (a fresh free-tier/trial project is fine).
2. [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5.
3. [gcloud CLI](https://cloud.google.com/sdk/docs/install), authenticated:
   ```bash
   gcloud auth application-default login
   ```

## Usage

```bash
cd infra/terraform
terraform init
terraform plan \
  -var="project_id=<your-project-id>" \
  -var="raw_bucket_name=<your-project-id>-retail-demand-raw"
terraform apply \
  -var="project_id=<your-project-id>" \
  -var="raw_bucket_name=<your-project-id>-retail-demand-raw"
```

Or copy the variables into a `terraform.tfvars` file (gitignored) instead of
passing `-var` flags each time.

## Cost notes

- BigQuery: 10 GB storage + 1 TB query/month are free; this dataset (a subset
  of M5) stays well under that if you don't materialize every mart as a full
  table repeatedly.
- GCS: the raw bucket has a 30-day lifecycle rule to auto-delete objects,
  since BigQuery is the durable copy once loaded.
- Nothing here is always-on/billed-by-the-hour — no Cloud Composer, no
  standing Vertex AI endpoint. Costs only occur when you run a job.
- Run `terraform destroy` when you're done experimenting to avoid any
  lingering storage cost.
