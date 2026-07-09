import pandas as pd

from retail_demand.models.evaluate import (
    evaluate_predictions,
    rmsse_per_series,
    weighted_rmsse,
)


def _series(store_id, item_id, dates, sales):
    return pd.DataFrame({"date": dates, "store_id": store_id, "item_id": item_id, "sales": sales})


def test_rmsse_is_zero_for_perfect_forecast():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    train = _series("CA_1", "A", dates, [1, 2, 3, 4, 5])
    future_dates = pd.date_range("2024-01-06", periods=2, freq="D")
    actual = _series("CA_1", "A", future_dates, [6, 7])
    forecast = actual.copy()

    per_series = rmsse_per_series(actual, forecast, train)

    assert per_series.loc[0, "rmsse"] == 0.0
    assert per_series.loc[0, "total_sales"] == 15.0


def test_rmsse_penalizes_worse_than_naive_scale():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    # constant training series -> naive-step scale is 0 -> falls back to scale=1.0
    train = _series("CA_1", "A", dates, [3, 3, 3, 3, 3])
    future_dates = pd.date_range("2024-01-06", periods=1, freq="D")
    actual = _series("CA_1", "A", future_dates, [3])
    forecast = _series("CA_1", "A", future_dates, [5])

    per_series = rmsse_per_series(actual, forecast, train)
    assert per_series.loc[0, "rmsse"] == 2.0  # sqrt((3-5)^2 / 1.0)


def test_weighted_rmsse_weights_by_total_sales():
    per_series = pd.DataFrame(
        {
            "store_id": ["CA_1", "CA_1"],
            "item_id": ["A", "B"],
            "rmsse": [0.0, 2.0],
            "total_sales": [100.0, 0.0],
        }
    )
    # B has zero weight, so the weighted average should equal A's rmsse (0.0),
    # not the plain mean (1.0).
    assert weighted_rmsse(per_series) == 0.0


def test_weighted_rmsse_falls_back_to_mean_when_all_weights_zero():
    per_series = pd.DataFrame(
        {
            "store_id": ["CA_1", "CA_1"],
            "item_id": ["A", "B"],
            "rmsse": [1.0, 3.0],
            "total_sales": [0.0, 0.0],
        }
    )
    assert weighted_rmsse(per_series) == 2.0


def test_evaluate_predictions_returns_all_metrics():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    train = _series("CA_1", "A", dates, [1, 2, 3, 4, 5])
    future_dates = pd.date_range("2024-01-06", periods=2, freq="D")
    actual = _series("CA_1", "A", future_dates, [6, 7])
    forecast = _series("CA_1", "A", future_dates, [5, 8])

    result = evaluate_predictions(actual, forecast, train)

    assert set(result.keys()) == {"mape", "rmse", "wrmsse", "n", "n_series"}
    assert result["n"] == 2
    assert result["n_series"] == 1
