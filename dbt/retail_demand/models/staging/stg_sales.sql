-- Unions the frozen historical load with the ongoing synthetic daily feed
-- into one core fact grain: (date, store_id, item_id, sales). Item/store
-- attributes live in dim_item / dim_store, not here. sell_price is null for
-- historical rows (fct_sales gets their real price via the prices join
-- instead) and forward-filled for feed rows - see stg_sales_daily_feed.
select date, store_id, item_id, sales, cast(null as float64) as sell_price
from {{ ref('stg_sales_history') }}

union all

select date, store_id, item_id, sales, sell_price
from {{ ref('stg_sales_daily_feed') }}
