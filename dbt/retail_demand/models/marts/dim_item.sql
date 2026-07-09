select distinct
    item_id,
    dept_id,
    cat_id
from {{ ref('stg_sales_history') }}
