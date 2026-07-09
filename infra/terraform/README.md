# Terraform — base GCP infra

Provisions the shared infra: raw GCS bucket, BigQuery datasets
(raw/staging/marts), an Artifact Registry Docker repo, a service account for
pipeline/training/CI jobs, and a Cloud Build trigger that builds the pipeline
image and submits a Vertex AI training run on push to `master`. Cloud Run
services and the Cloud Scheduler retraining trigger are added in later
phases (once those components exist) rather than provisioned up front.

**Not yet applied** — this requires your own GCP project and billing, and
hasn't been validated with `terraform validate`/`plan` either (the
`terraform` CLI isn't installed in this development environment). Nothing in
this repo has touched real cloud resources.

## Prerequisites

1. A GCP project with billing enabled (a fresh free-tier/trial project is fine).
2. [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5.
3. [gcloud CLI](https://cloud.google.com/sdk/docs/install), authenticated:
   ```bash
   gcloud auth application-default login
   ```
4. For the Cloud Build trigger only: install the "Google Cloud Build"
   GitHub App on this repo once, manually, via the Cloud Build console
   (Triggers -> Connect Repository -> GitHub). Terraform can create the
   trigger resource itself, but the initial GitHub OAuth connection is a
   one-time console step it can't do for you.

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
passing `-var` flags each time. `github_owner`/`github_repo_name` default to
this repo's own GitHub location, so you only need to override them if you've
forked it elsewhere.

To trigger a build manually without waiting for a push (useful while
testing):

```bash
gcloud builds submit --config cloudbuild.yaml --project <your-project-id>
```

## Cost notes

- BigQuery: 10 GB storage + 1 TB query/month are free; this dataset (a subset
  of M5) stays well under that if you don't materialize every mart as a full
  table repeatedly.
- GCS: the raw bucket has a 30-day lifecycle rule to auto-delete objects,
  since BigQuery is the durable copy once loaded.
- Nothing here is always-on/billed-by-the-hour — no Cloud Composer, no
  standing Vertex AI endpoint. Costs only occur when you run a job.
- Cloud Build: 120 free build-minutes/day; building the pipeline image and
  submitting a training run on each push to master stays well within that
  for a project this size.
- Run `terraform destroy` when you're done experimenting to avoid any
  lingering storage cost.
