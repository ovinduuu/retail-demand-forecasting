# dbt project: retail_demand

Transforms raw M5 tables in BigQuery into staging views and mart tables.

```
raw.sales_history, raw.sales_daily_feed, raw.calendar, raw.sell_prices  (loaded by
    src/retail_demand/data_engineering/load_to_bigquery.py)
        │
        ▼
staging: stg_sales_history, stg_sales_daily_feed, stg_sales (union of both),
         stg_calendar, stg_prices
        │
        ▼
marts: dim_item, dim_store, dim_calendar, fct_sales
```

## One-time setup (needs a GCP project with BigQuery + the datasets created by
`infra/terraform`)

Create `~/.dbt/profiles.yml` (not checked into git):

```yaml
retail_demand:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: "{{ env_var('GCP_PROJECT_ID') }}"
      dataset: retail_demand_staging
      threads: 4
      location: US
```

Then, from `dbt/retail_demand/`:

```bash
dbt deps
dbt run
dbt test
```

Verified end-to-end against a real GCP project: all 9 models build and all
10 data tests pass, including `fct_sales` at its real size (~58M rows).

### Python version note

`dbt-bigquery`'s `mashumaro` dependency currently fails to import on Python
3.14 (`UnserializableField` at import time — a real incompatibility with how
3.14 handles typing introspection, not a config issue). If your default
`uv`-managed Python is 3.14+, run dbt from a separate, older interpreter
instead of fighting the main project venv:

```bash
uv venv --python 3.12 .venv-dbt
uv pip install --python .venv-dbt dbt-bigquery
.venv-dbt/Scripts/dbt.exe run   # Windows; .venv-dbt/bin/dbt on Linux/Mac
```

The rest of this project's dependencies (pandas, lightgbm, fastapi, kfp,
...) work fine on 3.14 — this is specifically a `dbt-bigquery`/`mashumaro`
issue, not a reason to downgrade the whole project's Python version.
