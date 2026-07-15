-- Dates shifted by date_offset_days (see dbt_project.yml) - the raw table
-- stays in M5's original ("relative") time, same as stg_sales_history.
select
    date_add(cast(date as date), interval {{ var('date_offset_days') }} day) as date,
    store_id,
    item_id,
    cast(sales as int64) as sales
from {{ source('raw', 'sales_daily_feed') }}
