-- Dates shifted by date_offset_days (see dbt_project.yml) - the raw table
-- stays in M5's original ("relative") time, same as stg_sales_history.
-- sell_price is nullable: only rows daily_ingest.py wrote have it
-- (forward-filled from each series' last known price); null for the one
-- legacy row loaded before that column existed.
select
    date_add(cast(date as date), interval {{ var('date_offset_days') }} day) as date,
    store_id,
    item_id,
    cast(sales as int64) as sales,
    safe_cast(sell_price as float64) as sell_price
from {{ source('raw', 'sales_daily_feed') }}
