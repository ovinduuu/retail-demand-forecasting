-- One row per prediction that has a matching actual. Inner join means a
-- prediction only shows up here once that date's real sales have landed
-- (via data_engineering/daily_ingest.py) - naturally lags predictions by
-- however long that takes, rather than needing an explicit "is this ready
-- yet" check.
with predictions as (
    select date, store_id, item_id, predicted_sales
    from {{ source('marts_raw', 'fct_sales_predictions') }}
),

actuals as (
    select date, store_id, item_id, sales
    from {{ ref('fct_sales') }}
)

select
    predictions.date,
    predictions.store_id,
    predictions.item_id,
    predictions.predicted_sales,
    actuals.sales as actual_sales,
    abs(predictions.predicted_sales - actuals.sales) as abs_error,
    case
        when actuals.sales > 0
            then abs(predictions.predicted_sales - actuals.sales) / actuals.sales
    end as pct_error
from predictions
inner join actuals
    on predictions.date = actuals.date
    and predictions.store_id = actuals.store_id
    and predictions.item_id = actuals.item_id
