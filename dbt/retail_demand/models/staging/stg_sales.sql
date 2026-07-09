-- Unions the frozen historical load with the ongoing synthetic daily feed
-- into one core fact grain: (date, store_id, item_id, sales). Item/store
-- attributes live in dim_item / dim_store, not here.
select date, store_id, item_id, sales
from {{ ref('stg_sales_history') }}

union all

select date, store_id, item_id, sales
from {{ ref('stg_sales_daily_feed') }}
