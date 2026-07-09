select
    cast(date as date) as date,
    wm_yr_wk,
    weekday,
    cast(wday as int64) as wday,
    cast(month as int64) as month,
    cast(year as int64) as year,
    event_name_1,
    event_type_1,
    event_name_2,
    event_type_2,
    cast(snap_ca as int64) as snap_ca,
    cast(snap_tx as int64) as snap_tx,
    cast(snap_wi as int64) as snap_wi
from {{ source('raw', 'calendar') }}
