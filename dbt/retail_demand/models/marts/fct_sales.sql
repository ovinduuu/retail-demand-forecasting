with sales as (
    select * from {{ ref('stg_sales') }}
),

calendar as (
    select * from {{ ref('dim_calendar') }}
),

prices as (
    select * from {{ ref('stg_prices') }}
),

stores as (
    select * from {{ ref('dim_store') }}
)

select
    sales.date,
    sales.store_id,
    sales.item_id,
    sales.sales,
    prices.sell_price,
    calendar.wday,
    calendar.month,
    calendar.year,
    calendar.event_name_1,
    calendar.event_type_1,
    case stores.state_id
        when 'CA' then calendar.snap_ca
        when 'TX' then calendar.snap_tx
        when 'WI' then calendar.snap_wi
    end as snap_flag
from sales
left join calendar on sales.date = calendar.date
left join stores on sales.store_id = stores.store_id
left join prices
    on sales.store_id = prices.store_id
    and sales.item_id = prices.item_id
    and calendar.wm_yr_wk = prices.wm_yr_wk
