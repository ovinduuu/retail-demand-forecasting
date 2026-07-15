import datetime as dt

from retail_demand.data_engineering.daily_ingest import days_to_generate


def test_days_to_generate_empty_when_already_caught_up():
    assert days_to_generate(dt.date(2026, 7, 13), dt.date(2026, 7, 13)) == []
    assert days_to_generate(dt.date(2026, 7, 14), dt.date(2026, 7, 13)) == []


def test_days_to_generate_single_day_normal_case():
    result = days_to_generate(dt.date(2026, 7, 12), dt.date(2026, 7, 13))
    assert result == [dt.date(2026, 7, 13)]


def test_days_to_generate_covers_a_missed_gap():
    result = days_to_generate(dt.date(2026, 7, 10), dt.date(2026, 7, 13))
    assert result == [dt.date(2026, 7, 11), dt.date(2026, 7, 12), dt.date(2026, 7, 13)]


def test_days_to_generate_caps_a_long_gap_to_the_oldest_days():
    result = days_to_generate(dt.date(2026, 1, 1), dt.date(2026, 7, 13), max_days=5)
    assert result == [dt.date(2026, 1, i) for i in range(2, 7)]
