import argparse

import pytest

pytest.importorskip("kfp")

from retail_demand.pipelines.submit_pipeline import (  # noqa: E402
    build_parameter_values,
    compile_pipeline,
    resolve_date_range,
)


def test_resolve_date_range_defaults_both():
    start, end = resolve_date_range(None, None, lookback_days=730)
    import datetime as dt

    assert end == dt.datetime.now(dt.timezone.utc).date().isoformat()
    assert dt.date.fromisoformat(end) - dt.date.fromisoformat(start) == dt.timedelta(days=730)


def test_resolve_date_range_uses_explicit_end_for_default_start():
    start, end = resolve_date_range(None, "2024-06-01", lookback_days=365)
    assert end == "2024-06-01"
    assert start == "2023-06-02"


def test_resolve_date_range_respects_explicit_start():
    start, end = resolve_date_range("2020-01-01", "2024-06-01")
    assert start == "2020-01-01"
    assert end == "2024-06-01"


def _make_args(**overrides) -> argparse.Namespace:
    defaults = dict(
        project_id="my-project",
        region="us-central1",
        start_date=None,
        end_date="2024-06-01",
        serving_container_image_uri="us-central1-docker.pkg.dev/my-project/retail-demand/serving:latest",
        bq_location="US",
        valid_days=28,
        wrmsse_threshold=1.0,
        model_display_name="retail-demand-lightgbm",
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_build_parameter_values_includes_all_pipeline_params():
    params = build_parameter_values(_make_args())

    assert params["project_id"] == "my-project"
    assert params["region"] == "us-central1"
    assert params["end_date"] == "2024-06-01"
    assert params["start_date"] == "2022-06-02"
    assert params["serving_container_image_uri"].startswith("us-central1-docker.pkg.dev")
    assert params["valid_days"] == 28
    assert params["wrmsse_threshold"] == 1.0


def test_compile_pipeline_writes_valid_spec(tmp_path):
    out_path = tmp_path / "pipeline.yaml"
    result = compile_pipeline(str(out_path))

    assert result == str(out_path)
    assert out_path.exists()
