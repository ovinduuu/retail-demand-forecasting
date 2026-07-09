# Image used by the Vertex AI Pipeline components in
# src/retail_demand/pipelines/. Bundles the retail_demand package (gcp + ml
# extras), the dbt project, and dbt-bigquery, so every pipeline step —
# dbt transform, feature build, train, register — runs from one image
# instead of juggling several.
#
# Not yet built/pushed anywhere: that needs the Artifact Registry repo from
# infra/terraform applied first, then:
#   docker build -t <region>-docker.pkg.dev/<project>/retail-demand/pipeline:latest .
#   docker push <region>-docker.pkg.dev/<project>/retail-demand/pipeline:latest
# (see infra/terraform/README.md for the repo Terraform provisions).

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY dbt ./dbt

RUN pip install --no-cache-dir ".[gcp,ml]" dbt-bigquery

ENV PYTHONUNBUFFERED=1
