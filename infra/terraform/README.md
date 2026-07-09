# Terraform — GCP infra

Provisions the shared infra: raw GCS bucket, BigQuery datasets
(raw/staging/marts), an Artifact Registry Docker repo, a service account for
pipeline/training/CI jobs, and a Cloud Build trigger that builds the pipeline
image and submits a Vertex AI training run on push to `master`.

Several resource groups are conditional on an image already existing, so
the base infra can be applied before any images are built:

- `google_cloud_run_v2_service.serving` — the optional live-request demo,
  created only once `serving_image_uri` is set.
- `google_cloud_run_v2_job.batch_predict` + its `google_cloud_scheduler_job`
  — the primary daily batch-scoring path, created only once
  `pipeline_image_uri` is set.
- `google_cloud_run_v2_job.drift_check` + its scheduler — daily feature
  drift check, logged to BigQuery, created once `pipeline_image_uri` is set.
- `google_cloud_run_v2_job.retrain_trigger` + its scheduler — reads the
  latest drift/metrics and submits a new training pipeline run if either
  regressed, created once both `pipeline_image_uri` and `serving_image_uri`
  are set (a triggered retrain needs a serving image to register against).

See `docs/monitoring.md` for what these two jobs log and how to build a
dashboard on top of it.

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

Once both images exist (built by the Cloud Build trigger above, or manually
via `docker build`/`docker push`), re-apply with the image variables set to
create the serving Cloud Run service, and the batch-predict, drift-check,
and retrain-trigger Cloud Run Jobs + their schedulers:

```bash
terraform apply \
  -var="project_id=<your-project-id>" \
  -var="raw_bucket_name=<your-project-id>-retail-demand-raw" \
  -var="pipeline_image_uri=<region>-docker.pkg.dev/<your-project-id>/retail-demand/pipeline:latest" \
  -var="serving_image_uri=<region>-docker.pkg.dev/<your-project-id>/retail-demand/serving:latest"
```

## Cost notes

See [`docs/costs.md`](../../docs/costs.md) for the full per-service
breakdown. Two terraform-specific things worth knowing:

- No public IAM binding is created for the serving Cloud Run service by
  default (`min_instance_count = 0` too), so it isn't reachable — or
  billable from stray traffic — until you explicitly grant
  `roles/run.invoker` to `allUsers`.
- Run `terraform destroy` when you're done experimenting to avoid any
  lingering storage cost.
