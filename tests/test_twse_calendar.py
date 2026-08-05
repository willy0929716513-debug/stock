import datetime as dt

from src.data.providers.twse_calendar import is_trading_day


def test_weekday_not_in_holiday_list_is_trading_day():
    # 2026-08-05 是週三,不在休市清單中
    assert is_trading_day(dt.date(2026, 8, 5)) is True


def test_saturday_is_not_trading_day():
    # 2026-08-08 是週六
    assert is_trading_day(dt.date(2026, 8, 8)) is False


def test_sunday_is_not_trading_day():
    # 2026-08-09 是週日
    assert is_trading_day(dt.date(2026, 8, 9)) is False


def test_new_years_day_is_not_trading_day():
    assert is_trading_day(dt.date(2026, 1, 1)) is False


def test_custom_holiday_set_overrides_default():
    custom_holidays = {"2026-08-05"}
    assert is_trading_day(dt.date(2026, 8, 5), holidays=custom_holidays) is False
