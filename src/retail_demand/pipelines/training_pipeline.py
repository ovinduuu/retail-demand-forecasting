"""Vertex AI Pipeline (KFP v2): dbt transform -> extract training data ->
train -> conditionally register in Vertex AI Model Registry.

Written and locally compilable (see tests/test_training_pipeline.py and
`make compile-pipeline`), but not yet submitted to a real Vertex AI Pipelines
run — that needs infra/terraform applied, PIPELINE_IMAGE built and pushed to
the resulting Artifact Registry repo (see ../../../Dockerfile), and a
serving_container_image_uri from Phase 6.

Usage:
    uv run python -m retail_demand.pipelines.training_pipeline --out pipeline.json
"""

import argparse
from pathlib import Path

from kfp import compiler, dsl

from retail_demand.pipelines.components import (
    extract_training_data,
    register_model,
    run_dbt_transform,
    train_model,
)

DEFAULT_WRMSSE_THRESHOLD = 1.0


@dsl.pipeline(name="retail-demand-training")
def training_pipeline(
    project_id: str,
    region: str,
    start_date: str,
    end_date: str,
    serving_container_image_uri: str,
    serving_model_gcs_path: str,
    bq_location: str = "US",
    valid_days: int = 28,
    weight_dampening: str = "none",
    wrmsse_threshold: float = DEFAULT_WRMSSE_THRESHOLD,
    model_display_name: str = "retail-demand-lightgbm",
) -> None:
    dbt_task = run_dbt_transform(project_id=project_id, bq_location=bq_location)

    extract_task = extract_training_data(
        project_id=project_id, start_date=start_date, end_date=end_date
    )
    extract_task.after(dbt_task)

    train_task = train_model(
        training_data=extract_task.outputs["training_data"],
        project_id=project_id,
        valid_days=valid_days,
        weight_dampening=weight_dampening,
    )
    # Default Vertex machine OOM'd once the feature set grew (lag_1/2/3,
    # rolling std, days_since_last_sale) on the full ~20M-row training
    # extract - explicit headroom instead of relying on the default.
    train_task.set_cpu_limit("8")
    train_task.set_memory_limit("32G")

    with dsl.If(train_task.outputs["wrmsse"] < wrmsse_threshold, name="wrmsse-improved"):
        register_model(
            model=train_task.outputs["model"],
            project_id=project_id,
            region=region,
            serving_container_image_uri=serving_container_image_uri,
            serving_model_gcs_path=serving_model_gcs_path,
            display_name=model_display_name,
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="artifacts/training_pipeline.yaml")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    compiler.Compiler().compile(training_pipeline, package_path=args.out)
    print(f"Compiled pipeline spec to {args.out}")


if __name__ == "__main__":
    main()
