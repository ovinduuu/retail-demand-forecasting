# Serving image for src/retail_demand/serving/app.py - the optional Cloud
# Run live-request demo, and the serving_container_image_uri Phase 4's
# register_model needs. Deliberately smaller than the root Dockerfile: no
# dbt, just what app.py needs to load a model, query BigQuery for the
# /series /history /forecast routes (see app.py), and serve predictions.
#
# Not yet built/pushed: needs infra/terraform's Artifact Registry repo, then
# (from the repo root, since this needs pyproject.toml/src as build context):
#   docker build -f docker/serving.Dockerfile \
#     -t <region>-docker.pkg.dev/<project>/retail-demand/serving:latest .
#   docker push <region>-docker.pkg.dev/<project>/retail-demand/serving:latest

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN pip install --no-cache-dir ".[ml,serving,gcp]"

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["uvicorn", "retail_demand.serving.app:app", "--host", "0.0.0.0", "--port", "8080"]
