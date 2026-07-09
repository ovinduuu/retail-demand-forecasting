"""Compile the training pipeline (training_pipeline.py) and submit it as a
Vertex AI Pipeline Job.

This is what cloudbuild.yaml calls after building/pushing the pipeline
image. Not yet run against a real GCP project - needs infra/terraform
applied and the image pushed to the Artifact Registry it provisions.

Usage:
    uv run python -m retail_demand.pipelines.submit_pipeline \\
        --project-id my-project --region us-central1 \\
        --pipeline-root gs://my-project-retail-demand-raw/pipeline-root \\
        --serving-container-image-uri \\
        us-central1-docker.pkg.dev/my-project/retail-demand/serving:latest
"""

import argparse
import datetime as dt
from pathlib import Path

from retail_demand.pipelines.training_pipeline import (
    DEFAULT_WRMSSE_THRESHOLD,
    training_pipeline,
)

DEFAULT_LOOKBACK_DAYS = 730  # ~2 years of history to train on, by default


def resolve_date_range(
    start_date: str | None, end_date: str | None, lookback_days: int = DEFAULT_LOOKBACK_DAYS
) -> tuple[str, str]:
    """Fill in missing start/end dates: end defaults to today (UTC), start to
    `lookback_days` before whichever end date is in effect."""
    resolved_end = end_date or dt.datetime.now(dt.timezone.utc).date().isoformat()
    if start_date:
        resolved_start = start_date
    else:
        resolved_start = (
            dt.date.fromisoformat(resolved_end) - dt.timedelta(days=lookback_days)
        ).isoformat()
    return resolved_start, resolved_end


def build_parameter_values(args: argparse.Namespace) -> dict:
    """Build the Vertex AI pipeline's parameter_values dict from parsed CLI args.

    Split out from main() so it's unit-testable without GCP credentials.
    """
    start_date, end_date = resolve_date_range(args.start_date, args.end_date)
    return {
        "project_id": args.project_id,
        "region": args.region,
        "start_date": start_date,
        "end_date": end_date,
        "serving_container_image_uri": args.serving_container_image_uri,
        "serving_model_gcs_path": args.serving_model_gcs_path,
        "bq_location": args.bq_location,
        "valid_days": args.valid_days,
        "wrmsse_threshold": args.wrmsse_threshold,
        "model_display_name": args.model_display_name,
    }


def compile_pipeline(out_path: str) -> str:
    from kfp import compiler

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    compiler.Compiler().compile(training_pipeline, package_path=out_path)
    return out_path


def submit_pipeline_job(
    compiled_path: str,
    parameter_values: dict,
    project_id: str,
    region: str,
    pipeline_root: str,
    job_id: str | None = None,
    enable_caching: bool = True,
):
    from google.cloud import aiplatform

    aiplatform.init(project=project_id, location=region)
    job = aiplatform.PipelineJob(
        display_name="retail-demand-training",
        template_path=compiled_path,
        pipeline_root=pipeline_root,
        parameter_values=parameter_values,
        job_id=job_id,
        enable_caching=enable_caching,
    )
    job.submit()
    return job


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--region", default="us-central1")
    parser.add_argument(
        "--pipeline-root",
        required=True,
        help="GCS path Vertex uses to stage pipeline artifacts, e.g. gs://<bucket>/pipeline-root",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help=f"Defaults to {DEFAULT_LOOKBACK_DAYS} days before --end-date.",
    )
    parser.add_argument("--end-date", default=None, help="Defaults to today (UTC).")
    parser.add_argument("--serving-container-image-uri", required=True)
    parser.add_argument(
        "--serving-model-gcs-path",
        required=True,
        help="Fixed gs:// path batch_predict.py's Cloud Run Job reads the model from.",
    )
    parser.add_argument("--bq-location", default="US")
    parser.add_argument("--valid-days", type=int, default=28)
    parser.add_argument("--wrmsse-threshold", type=float, default=DEFAULT_WRMSSE_THRESHOLD)
    parser.add_argument("--model-display-name", default="retail-demand-lightgbm")
    parser.add_argument("--compiled-path", default="artifacts/training_pipeline.yaml")
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--no-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    compiled_path = compile_pipeline(args.compiled_path)
    parameter_values = build_parameter_values(args)

    job = submit_pipeline_job(
        compiled_path,
        parameter_values,
        project_id=args.project_id,
        region=args.region,
        pipeline_root=args.pipeline_root,
        job_id=args.job_id,
        enable_caching=not args.no_cache,
    )
    print(f"Submitted pipeline job: {job.resource_name}")


if __name__ == "__main__":
    main()
