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

This has not been run yet in this repo — it requires a real GCP project and
the raw tables to already be loaded (see `data/README.md` and
`infra/terraform/README.md`).
