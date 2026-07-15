"""Simulate an ongoing daily sales feed on top of the static M5 history.

The M5 dataset is a frozen historical snapshot. To exercise the data
engineering / MLOps pipeline the way a real retailer would (new rows landing
every day), this module fabricates one plausible "new day" of sales per
item-store pair, extrapolated from that series' recent seasonality plus
noise, rather than replaying held-out real data.

Intended usage: run on a schedule (locally via `make synth-data`; on GCP via
Cloud Scheduler -> Cloud Function in a later phase) to append a new day's
rows to the raw BigQuery table.
"""

from __future__ import annotations

import argparse
import datetime as dt

import numpy as np
import pandas as pd

DAYS_PER_WEEK = 7


def _seasonal_baseline(history: pd.Series, weekday: int, lookback_weeks: int = 8) -> float:
    """Average of the same weekday over the last `lookback_weeks` weeks of history."""
    if history.empty:
        return 0.0
    same_weekday = history.iloc[-1 : -(lookback_weeks * DAYS_PER_WEEK + 1) : -DAYS_PER_WEEK]
    if same_weekday.empty:
        same_weekday = history.tail(DAYS_PER_WEEK)
    return float(same_weekday.mean())


def generate_next_day(
    history: pd.DataFrame,
    as_of_date: dt.date,
    noise_std_frac: float = 0.15,
    rng: np.random.Generator | None = None,
) -> pd.DataFrame:
    """Generate one new day of synthetic sales rows from historical sales.

    Args:
        history: long-format DataFrame with columns ["date", "store_id",
            "item_id", "sales"], sorted by date, one row per (date, store, item).
            An optional "sell_price" column, if present, is forward-filled
            into the new day (each series' most recent known price carried
            unchanged) - real price data runs out once synthetic days
            outpace M5's calendar range, and price has genuine day-to-day
            continuity (unlike a one-off SNAP/event flag), so carrying it
            forward is more realistic than leaving it null.
        as_of_date: the calendar date to generate sales for.
        noise_std_frac: relative std-dev of the multiplicative noise applied
            to each series' seasonal baseline.
        rng: optional numpy Generator for reproducibility.

    Returns:
        DataFrame with the same columns as `history`, one row per
        (store_id, item_id) present in `history`, dated `as_of_date`.
    """
    if rng is None:
        rng = np.random.default_rng()

    has_price = "sell_price" in history.columns
    weekday = as_of_date.weekday()
    rows = []
    for (store_id, item_id), series in history.groupby(["store_id", "item_id"]):
        series = series.sort_values("date")
        baseline = _seasonal_baseline(series["sales"], weekday)
        noise = rng.normal(loc=1.0, scale=noise_std_frac)
        sales = max(0, round(baseline * max(noise, 0.0)))
        row = {
            "date": as_of_date,
            "store_id": store_id,
            "item_id": item_id,
            "sales": sales,
        }
        if has_price:
            known_prices = series["sell_price"].dropna()
            row["sell_price"] = float(known_prices.iloc[-1]) if not known_prices.empty else None
        rows.append(row)

    columns = ["date", "store_id", "item_id", "sales"] + (["sell_price"] if has_price else [])
    return pd.DataFrame(rows, columns=columns)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history",
        default="data/raw/sales_history.csv",
        help="Path to a CSV with columns [date, store_id, item_id, sales].",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output CSV path. Defaults to data/raw/synthetic_day_<date>.csv",
    )
    parser.add_argument(
        "--as-of-date",
        default=None,
        help="YYYY-MM-DD to generate. Defaults to the day after the max date in history.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    history = pd.read_csv(args.history, parse_dates=["date"])
    history["date"] = history["date"].dt.date

    if args.as_of_date:
        as_of_date = dt.date.fromisoformat(args.as_of_date)
    else:
        as_of_date = max(history["date"]) + dt.timedelta(days=1)

    new_day = generate_next_day(history, as_of_date)

    out_path = args.out or f"data/raw/synthetic_day_{as_of_date.isoformat()}.csv"
    new_day.to_csv(out_path, index=False)
    print(f"Wrote {len(new_day)} rows for {as_of_date} to {out_path}")


if __name__ == "__main__":
    main()
