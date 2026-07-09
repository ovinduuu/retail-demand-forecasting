"""Reshape the raw M5 files into the long format used everywhere else in this
project: one row per (date, store_id, item_id).

sales_train_validation.csv ships wide (one column per day: d_1, d_2, ...).
This melts it to long and joins in the real calendar date for each d_<n>
column, producing data/raw/sales_history.csv, which is what
synthetic_daily_feed.py and load_to_bigquery.py expect.

Usage:
    uv run python -m retail_demand.data_engineering.prepare_m5
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from retail_demand.config import DATA_RAW_DIR

ID_COLS = ["item_id", "dept_id", "cat_id", "store_id", "state_id"]


def melt_sales(sales_wide: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    """Melt wide sales_train_validation rows into long (date, store_id, item_id, sales)."""
    day_cols = [c for c in sales_wide.columns if c.startswith("d_")]
    long_df = sales_wide.melt(
        id_vars=ID_COLS, value_vars=day_cols, var_name="d", value_name="sales"
    )
    day_to_date = calendar.set_index("d")["date"]
    long_df["date"] = long_df["d"].map(day_to_date)
    long_df = long_df.dropna(subset=["date"])
    return long_df[["date", "store_id", "item_id", "dept_id", "cat_id", "state_id", "sales"]]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default=str(DATA_RAW_DIR))
    parser.add_argument("--out", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    raw_dir = Path(args.raw_dir)

    sales_wide = pd.read_csv(raw_dir / "sales_train_validation.csv")
    calendar = pd.read_csv(raw_dir / "calendar.csv", parse_dates=["date"])

    long_df = melt_sales(sales_wide, calendar)

    out_path = Path(args.out) if args.out else raw_dir / "sales_history.csv"
    long_df.to_csv(out_path, index=False)
    print(f"Wrote {len(long_df)} rows to {out_path}")


if __name__ == "__main__":
    main()
