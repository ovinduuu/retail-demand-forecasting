import pandas as pd
import pytest

pytest.importorskip("kfp")  # retrain_trigger imports submit_pipeline, which imports kfp

from retail_demand.monitoring.retrain_trigger import (  # noqa: E402
    should_retrain,
    should_retrain_from_drift,
    should_retrain_from_metrics,
)


def _drift_df(*flags: bool) -> pd.DataFrame:
    return pd.DataFrame({"feature": [f"f{i}" for i in range(len(flags))], "drifted": flags})


def test_should_retrain_from_drift_true_when_enough_features_drifted():
    assert should_retrain_from_drift(_drift_df(True, False, False), min_drifted_features=1)
    assert not should_retrain_from_drift(_drift_df(True, False, False), min_drifted_features=2)


def test_should_retrain_from_drift_false_for_empty_or_missing_column():
    assert not should_retrain_from_drift(pd.DataFrame())
    assert not should_retrain_from_drift(pd.DataFrame({"feature": ["f0"]}))


def test_should_retrain_from_metrics_true_when_over_threshold():
    assert should_retrain_from_metrics(1.5, threshold=1.0)
    assert not should_retrain_from_metrics(0.5, threshold=1.0)


def test_should_retrain_from_metrics_false_when_unknown():
    assert not should_retrain_from_metrics(None, threshold=1.0)


def test_should_retrain_combines_drift_and_metrics_with_or():
    no_drift = _drift_df(False, False)
    some_drift = _drift_df(True, False)

    assert should_retrain(some_drift, latest_wrmsse=0.1, wrmsse_threshold=1.0)  # drift alone
    assert should_retrain(no_drift, latest_wrmsse=2.0, wrmsse_threshold=1.0)  # metrics alone
    assert not should_retrain(no_drift, latest_wrmsse=0.1, wrmsse_threshold=1.0)  # neither
    assert should_retrain(some_drift, latest_wrmsse=2.0, wrmsse_threshold=1.0)  # both
