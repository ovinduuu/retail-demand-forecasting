select
    date,
    wm_yr_wk,
    weekday,
    wday,
    month,
    year,
    event_name_1,
    event_type_1,
    event_name_2,
    event_type_2,
    snap_ca,
    snap_tx,
    snap_wi
from {{ ref('stg_calendar') }}
