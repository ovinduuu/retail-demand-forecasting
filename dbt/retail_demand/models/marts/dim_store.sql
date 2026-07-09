select distinct
    store_id,
    state_id
from {{ ref('stg_sales_history') }}
