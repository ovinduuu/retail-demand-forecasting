import datetime as dt

import numpy as np
import pandas as pd

from retail_demand.models.baseline import (
    mape,
    naive_forecast,
    rmse,
    score_forecast,
    seasonal_naive_forecast,
)


def _make_history(days: int = 14) -> pd.DataFrame:
    start = dt.date(2024, 1, 1)
    rows = []
    for store_id, item_id in [("CA_1", "FOODS_1_001"), ("CA_1", "FOODS_1_002")]:
        for i in range(days):
            rows.append(
                {
                    "date": pd.Timestamp(start + dt.timedelta(days=i)),
                    "store_id": store_id,
                    "item_id": item_id,
                    "sales": i % 7,
                }
            )
    return pd.DataFrame(rows)


def test_naive_forecast_repeats_last_value():
    history = _make_history()
    forecast = naive_forecast(history, horizon=3)

    assert len(forecast) == 2 * 3  # 2 series x 3-day horizon
    last_actual = history.sort_values("date").groupby(["store_id", "item_id"]).tail(1)
    for _, row in last_actual.iterrows():
        series_forecast = forecast[
            (forecast.store_id == row.store_id) & (forecast.item_id == row.item_id)
        ]
        assert (series_forecast["sales"] == row.sales).all()


def test_naive_forecast_dates_continue_from_history():
    history = _make_history()
    forecast = naive_forecast(history, horizon=2)
    last_date = history["date"].max()
    expected_dates = {last_date + pd.Timedelta(days=1), last_date + pd.Timedelta(days=2)}
    assert set(forecast["date"]) == expected_dates


def test_seasonal_naive_forecast_cycles_through_season():
    history = _make_history(days=14)
    forecast = seasonal_naive_forecast(history, horizon=7, season_length=7)

    one_series = forecast[
        (forecast.store_id == "CA_1") & (forecast.item_id == "FOODS_1_001")
    ].sort_values("date")
    # last 7 days of history are sales values [0,1,2,3,4,5,6] (day 7..13 % 7)
    assert list(one_series["sales"]) == [0, 1, 2, 3, 4, 5, 6]


def test_seasonal_naive_handles_short_history():
    history = _make_history(days=2)
    forecast = seasonal_naive_forecast(history, horizon=3, season_length=7)
    assert len(forecast) == 2 * 3
    assert (forecast["sales"] >= 0).all()


def test_mape_and_rmse_zero_for_perfect_forecast():
    y_true = np.array([1.0, 2.0, 3.0])
    assert mape(y_true, y_true) == 0.0
    assert rmse(y_true, y_true) == 0.0


def test_mape_uses_epsilon_floor_for_zero_actuals():
    y_true = np.array([0.0])
    y_pred = np.array([1.0])
    assert mape(y_true, y_pred, epsilon=1.0) == 1.0


def test_score_forecast_joins_and_scores():
    actual = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01")] * 2,
            "store_id": ["CA_1", "CA_1"],
            "item_id": ["A", "B"],
            "sales": [10, 20],
        }
    )
    forecast = actual.assign(sales=[8, 22])

    result = score_forecast(actual, forecast)

    assert result["n"] == 2
    assert result["rmse"] > 0
    assert result["mape"] > 0
