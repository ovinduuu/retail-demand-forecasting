"""Pure SQL-building helpers used by pipelines/components.py.

Deliberately kept in a module with no `kfp.dsl` decorators: components.py's
extract_training_data component imports from here at runtime (inside the
KFP executor, which re-imports whatever module a component's body pulls
in) - importing anything that re-triggers `@dsl.component(...)` decoration
crashes with `AttributeError: module 'kfp.dsl' has no attribute
'component'`, since the executor's runtime `kfp.dsl` doesn't expose the
authoring-time decorator API. Found the hard way: extract_training_data
originally imported build_extract_query from components.py itself, which
worked at local compile-time but failed the first time it actually ran on
Vertex AI.
"""


def build_extract_query(dataset: str, table: str, start_date: str, end_date: str) -> str:
    """SQL to pull one date range of the fct_sales mart for training."""
    return (
        "SELECT date, store_id, item_id, sales, sell_price, snap_flag, event_type_1 "
        f"FROM `{dataset}.{table}` "
        f"WHERE date BETWEEN '{start_date}' AND '{end_date}' "
        "ORDER BY store_id, item_id, date"
    )
