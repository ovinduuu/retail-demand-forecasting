-- Dates shifted by date_offset_days (see dbt_project.yml) so this frozen
-- M5 snapshot lands near real time instead of a decade in the past.
select
    date_add(cast(date as date), interval {{ var('date_offset_days') }} day) as date,
    store_id,
    item_id,
    dept_id,
    cat_id,
    state_id,
    cast(sales as int64) as sales
from {{ source('raw', 'sales_history') }}
