import datetime as dt

import numpy as np
import pandas as pd

from retail_demand.data_engineering.synthetic_daily_feed import (
    _seasonal_baseline,
    generate_next_day,
)


def _make_history(days: int = 28) -> pd.DataFrame:
    start = dt.date(2024, 1, 1)
    rows = []
    for store_id, item_id in [("CA_1", "FOODS_1_001"), ("CA_1", "FOODS_1_002")]:
        for i in range(days):
            rows.append(
                {
                    "date": start + dt.timedelta(days=i),
                    "store_id": store_id,
                    "item_id": item_id,
                    "sales": 10 + (i % 7),
                }
            )
    return pd.DataFrame(rows)


def test_seasonal_baseline_uses_same_weekday():
    history = _make_history()
    series = history[
        (history.store_id == "CA_1") & (history.item_id == "FOODS_1_001")
    ].sort_values("date")["sales"]
    baseline = _seasonal_baseline(series, weekday=0, lookback_weeks=4)
    assert baseline > 0


def test_seasonal_baseline_empty_history_returns_zero():
    assert _seasonal_baseline(pd.Series([], dtype=float), weekday=0) == 0.0


def test_generate_next_day_covers_all_series():
    history = _make_history()
    rng = np.random.default_rng(42)
    next_day = generate_next_day(
        history, as_of_date=dt.date(2024, 1, 29), rng=rng
    )

    assert set(next_day.columns) == {"date", "store_id", "item_id", "sales"}
    assert len(next_day) == history[["store_id", "item_id"]].drop_duplicates().shape[0]
    assert (next_day["date"] == dt.date(2024, 1, 29)).all()
    assert (next_day["sales"] >= 0).all()


def test_generate_next_day_is_reproducible_with_seed():
    history = _make_history()
    day1 = generate_next_day(history, dt.date(2024, 1, 29), rng=np.random.default_rng(7))
    day2 = generate_next_day(history, dt.date(2024, 1, 29), rng=np.random.default_rng(7))
    pd.testing.assert_frame_equal(day1, day2)
