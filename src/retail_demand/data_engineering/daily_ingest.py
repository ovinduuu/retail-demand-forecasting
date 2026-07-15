"""Daily data-landing job: appends new synthetic day(s) to the raw
sales_daily_feed table and refreshes the dbt marts, so fct_sales keeps pace
with real time.

Meant to run as a scheduled Cloud Run Job (see infra/terraform), earliest in
the daily chain - before drift-check, batch-predict, and retrain-trigger, so
they all see today's data.

Usage:
    uv run python -m retail_demand.data_engineering.daily_ingest \\
        --project-id my-project
"""

from __future__ import annotations

import argparse
import datetime as dt

import pandas as pd

from retail_demand.config import DATE_OFFSET_DAYS
from retail_demand.data_engineering.dbt_runner import run_dbt
from retail_demand.data_engineering.synthetic_daily_feed import generate_next_day

DEFAULT_LOOKBACK_DAYS = 90
DEFAULT_MAX_CATCHUP_DAYS = 14


def days_to_generate(
    latest_date: dt.date, target_date: dt.date, max_days: int = DEFAULT_MAX_CATCHUP_DAYS
) -> list[dt.date]:
    """Dates strictly after `latest_date` up to and including `target_date`,
    capped at `max_days` (oldest first) so a long-broken scheduler doesn't
    trigger a huge backfill in one run.
    """
    if target_date <= latest_date:
        return []
    gap = (target_date - latest_date).days
    all_days = [latest_date + dt.timedelta(days=i) for i in range(1, gap + 1)]
    if len(all_days) > max_days:
        print(f"WARNING: {len(all_days)} days behind, capping catch-up to {max_days}.")
        all_days = all_days[:max_days]
    return all_days


def _latest_fct_sales_date(project_id: str, dataset: str, table: str) -> dt.date:
    from google.cloud import bigquery

    client = bigquery.Client(project=project_id)
    row = list(client.query(f"SELECT MAX(date) AS max_date FROM `{dataset}.{table}`").result())[0]
    return row["max_date"]


def _load_recent_history(
    project_id: str, dataset: str, table: str, lookback_days: int
) -> pd.DataFrame:
    from google.cloud import bigquery

    client = bigquery.Client(project=project_id)
    query = (
        "SELECT date, store_id, item_id, sales, sell_price "
        f"FROM `{dataset}.{table}` "
        f"WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_days} DAY) "
        "ORDER BY store_id, item_id, date"
    )
    return client.query(query).to_dataframe()


def _write_feed_rows(project_id: str, dataset: str, table: str, rows: pd.DataFrame) -> None:
    from google.cloud import bigquery

    client = bigquery.Client(project=project_id)
    table_id = f"{project_id}.{dataset}.{table}"
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
    )
    job = client.load_table_from_dataframe(rows, table_id, job_config=job_config)
    job.result()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--marts-dataset", default="retail_demand_marts")
    parser.add_argument("--source-table", default="fct_sales")
    parser.add_argument("--raw-dataset", default="retail_demand_raw")
    parser.add_argument("--feed-table", default="sales_daily_feed")
    parser.add_argument("--bq-location", default="US")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--max-catchup-days", type=int, default=DEFAULT_MAX_CATCHUP_DAYS)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    latest_date = _latest_fct_sales_date(args.project_id, args.marts_dataset, args.source_table)
    target_date = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    targets = days_to_generate(latest_date, target_date, args.max_catchup_days)

    if not targets:
        print(f"Already caught up: fct_sales max date is {latest_date}, target is {target_date}.")
        return

    history = _load_recent_history(
        args.project_id, args.marts_dataset, args.source_table, args.lookback_days
    )
    new_days = []
    for target in targets:
        day = generate_next_day(history, target)
        new_days.append(day)
        history = pd.concat([history, day], ignore_index=True)

    feed_rows = pd.concat(new_days, ignore_index=True)
    # Raw sales_daily_feed stays in M5's original ("relative") time - dbt's
    # staging layer re-applies DATE_OFFSET_DAYS on every run (see
    # dbt_project.yml's date_offset_days var).
    feed_rows["date"] = feed_rows["date"].apply(
        lambda d: d - dt.timedelta(days=DATE_OFFSET_DAYS)
    )
    _write_feed_rows(args.project_id, args.raw_dataset, args.feed_table, feed_rows)
    print(f"Wrote {len(feed_rows)} rows for {len(targets)} day(s): {targets[0]} .. {targets[-1]}")

    run_dbt(args.project_id, args.bq_location)
    print("dbt run complete.")


if __name__ == "__main__":
    main()
