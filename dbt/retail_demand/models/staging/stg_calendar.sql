-- Dates shifted by date_offset_days (see dbt_project.yml). month/year are
-- re-derived from the shifted date rather than cast from the raw columns,
-- which would otherwise still describe the original (pre-shift) date.
-- weekday/wday need no such fix: date_offset_days is chosen as a multiple
-- of 7, so day-of-week is identical before and after the shift.
with shifted as (
    select
        date_add(cast(date as date), interval {{ var('date_offset_days') }} day) as date,
        wm_yr_wk,
        weekday,
        cast(wday as int64) as wday,
        event_name_1,
        event_type_1,
        event_name_2,
        event_type_2,
        cast(snap_ca as int64) as snap_ca,
        cast(snap_tx as int64) as snap_tx,
        cast(snap_wi as int64) as snap_wi
    from {{ source('raw', 'calendar') }}
)

select
    date,
    wm_yr_wk,
    weekday,
    wday,
    extract(month from date) as month,
    extract(year from date) as year,
    event_name_1,
    event_type_1,
    event_name_2,
    event_type_2,
    snap_ca,
    snap_tx,
    snap_wi
from shifted
