import pandas as pd

from retail_demand.data_engineering.prepare_m5 import melt_sales


def test_melt_sales_produces_long_format_with_correct_dates():
    sales_wide = pd.DataFrame(
        {
            "item_id": ["FOODS_1_001", "FOODS_1_002"],
            "dept_id": ["FOODS_1", "FOODS_1"],
            "cat_id": ["FOODS", "FOODS"],
            "store_id": ["CA_1", "CA_1"],
            "state_id": ["CA", "CA"],
            "d_1": [3, 0],
            "d_2": [5, 1],
        }
    )
    calendar = pd.DataFrame(
        {
            "d": ["d_1", "d_2"],
            "date": pd.to_datetime(["2011-01-29", "2011-01-30"]),
        }
    )

    long_df = melt_sales(sales_wide, calendar)

    assert set(long_df.columns) == {
        "date",
        "store_id",
        "item_id",
        "dept_id",
        "cat_id",
        "state_id",
        "sales",
    }
    assert len(long_df) == 4
    row = long_df[(long_df.item_id == "FOODS_1_001") & (long_df.date == pd.Timestamp("2011-01-29"))]
    assert row.iloc[0]["sales"] == 3
