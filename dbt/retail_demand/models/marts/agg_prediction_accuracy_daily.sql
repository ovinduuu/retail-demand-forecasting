-- One row per date, aggregated from fct_prediction_accuracy - cheap for the
-- serving API to read for a "model accuracy over time" chart, instead of
-- aggregating tens of thousands of per-series rows on every request.
select
    date,
    count(*) as n_predictions,
    avg(abs_error) as mae,
    avg(pct_error) as mape,
    sqrt(avg(power(predicted_sales - actual_sales, 2))) as rmse
from {{ ref('fct_prediction_accuracy') }}
group by date
order by date
