# Image used by the Vertex AI Pipeline components in
# src/retail_demand/pipelines/, and by the monitoring Cloud Run Jobs in
# src/retail_demand/monitoring/. Bundles the retail_demand package (gcp + ml
# + pipelines extras), the dbt project, and dbt-bigquery, so every pipeline
# step - dbt transform, feature build, train, register - and every
# monitoring job runs from one image instead of juggling several.
#
# The "pipelines" extra (google-cloud-aiplatform, kfp) is needed here, not
# just in cloudbuild.yaml's compile/submit step: register_model (running
# *inside* this image during a real pipeline execution) calls aiplatform
# directly, and retrain_trigger.py calls submit_pipeline.py's own
# aiplatform-based submission logic.
#
# Not yet built/pushed anywhere: that needs the Artifact Registry repo from
# infra/terraform applied first, then:
#   docker build -t <region>-docker.pkg.dev/<project>/retail-demand/pipeline:latest .
#   docker push <region>-docker.pkg.dev/<project>/retail-demand/pipeline:latest
# (see infra/terraform/README.md for the repo Terraform provisions).

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY dbt ./dbt

RUN pip install --no-cache-dir ".[gcp,ml,pipelines]" dbt-bigquery

ENV PYTHONUNBUFFERED=1
