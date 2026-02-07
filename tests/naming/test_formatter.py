from datetime import date

from naming.formatter import format_value


def test_date_without_format():
    d = date(2020, 1, 1)
    assert format_value(d, None) == "2020-01-01"


def test_date_with_year_format():
    d = date(2020, 1, 1)
    assert format_value(d, "yyyy") == "2020"


def test_none_value():
    assert format_value(None, None) is None
