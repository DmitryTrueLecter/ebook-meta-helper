from naming.renamer import build_filename
from tests.helpers.book_record_factory import make_record


def test_year_format():
    r = make_record(title="Book", year=2020)
    name = build_filename(r, "{Title} ({Published:yyyy})")
    assert name == "Book (2020)"


def test_full_date_format():
    r = make_record(title="Book", year=2020)
    name = build_filename(r, "{Published:yyyy-MM-dd}")
    assert name == "2020-01-01"
