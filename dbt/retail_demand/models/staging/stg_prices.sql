select
    store_id,
    item_id,
    wm_yr_wk,
    cast(sell_price as float64) as sell_price
from {{ source('raw', 'sell_prices') }}
