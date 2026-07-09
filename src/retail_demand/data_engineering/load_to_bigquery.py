"""Load raw M5 CSVs (and synthetic daily feed CSVs) from local disk / GCS into
BigQuery raw tables.

Requires GCP credentials with BigQuery + GCS access (e.g. `gcloud auth
application-default login`, or a service account key referenced via
GOOGLE_APPLICATION_CREDENTIALS) and the infra from infra/terraform applied
(dataset + bucket must already exist).

Usage:
    uv run python -m retail_demand.data_engineering.load_to_bigquery \
        --file data/raw/sales_train_validation.csv --table sales_train_validation
"""

from __future__ import annotations

import argparse
from pathlib import Path

from retail_demand.config import GCPConfig


def load_csv_to_bigquery(file_path: Path, table_name: str, cfg: GCPConfig) -> None:
    from google.cloud import bigquery

    client = bigquery.Client(project=cfg.project_id)
    table_id = f"{cfg.project_id}.{cfg.bq_dataset_raw}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    with open(file_path, "rb") as f:
        job = client.load_table_from_file(f, table_id, job_config=job_config)
    job.result()

    table = client.get_table(table_id)
    print(f"Loaded {file_path} -> {table_id} ({table.num_rows} rows total)")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Local CSV path to load.")
    parser.add_argument("--table", required=True, help="Destination BigQuery table name.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    load_csv_to_bigquery(Path(args.file), args.table, GCPConfig.from_env())
