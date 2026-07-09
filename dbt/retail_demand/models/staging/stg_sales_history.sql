select
    cast(date as date) as date,
    store_id,
    item_id,
    dept_id,
    cat_id,
    state_id,
    cast(sales as int64) as sales
from {{ source('raw', 'sales_history') }}
