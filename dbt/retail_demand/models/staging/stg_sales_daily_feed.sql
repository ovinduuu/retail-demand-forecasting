select
    cast(date as date) as date,
    store_id,
    item_id,
    cast(sales as int64) as sales
from {{ source('raw', 'sales_daily_feed') }}
