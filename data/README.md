# Data

`raw/` and `external/` are gitignored — nothing here is committed, only
downloaded/generated locally.

## Getting the M5 dataset

1. Create a Kaggle account if you don't have one, and join the
   [M5 Forecasting - Accuracy](https://www.kaggle.com/competitions/m5-forecasting-accuracy)
   competition (click "Late Submission" / accept rules — required before the
   API will let you download).
2. Get an API token: Kaggle → Settings → API → "Create New Token". This
   downloads `kaggle.json`.
3. Either:
   - place it at `~/.kaggle/kaggle.json` (Linux/Mac) or
     `C:\Users\<you>\.kaggle\kaggle.json` (Windows), or
   - copy `KAGGLE_USERNAME` / `KAGGLE_KEY` from it into your `.env`.
4. Install the data extras and download:
   ```bash
   uv sync --extra data
   uv run python -m retail_demand.data_engineering.download_m5
   ```
   This populates `data/raw/` with `sales_train_validation.csv`,
   `calendar.csv`, and `sell_prices.csv`.
5. Reshape the wide sales file into the long format the rest of the project
   uses:
   ```bash
   uv run python -m retail_demand.data_engineering.prepare_m5
   ```
   This writes `data/raw/sales_history.csv` (columns: date, store_id, item_id,
   dept_id, cat_id, state_id, sales).

## Simulating an ongoing feed

Once `sales_history.csv` exists, generate a synthetic "next day" of sales
(extrapolated from each series' recent seasonality, not real held-out data):

```bash
make synth-data
# or: uv run python -m retail_demand.data_engineering.synthetic_daily_feed
```

## Loading into BigQuery

Requires the infra in `infra/terraform` to be applied first (raw dataset must
exist), and GCP credentials available locally:

```bash
uv sync --extra gcp
uv run python -m retail_demand.data_engineering.load_to_bigquery \
  --file data/raw/sales_history.csv --table sales_history
uv run python -m retail_demand.data_engineering.load_to_bigquery \
  --file data/raw/calendar.csv --table calendar
uv run python -m retail_demand.data_engineering.load_to_bigquery \
  --file data/raw/sell_prices.csv --table sell_prices
```

Synthetic daily feed files load into a separate `sales_daily_feed` table
(unioned with history at the dbt staging layer):

```bash
uv run python -m retail_demand.data_engineering.load_to_bigquery \
  --file data/raw/synthetic_day_<date>.csv --table sales_daily_feed
```
