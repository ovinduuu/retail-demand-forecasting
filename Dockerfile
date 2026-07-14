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

# libgomp1: LightGBM's compiled library dlopen()s libgomp.so.1 (OpenMP) at
# import time - python:3.11-slim doesn't include it, so `import lightgbm`
# fails with "libgomp.so.1: cannot open shared object file" without this.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY dbt ./dbt

RUN pip install --no-cache-dir ".[gcp,ml,pipelines,dbt]"

ENV PYTHONUNBUFFERED=1
