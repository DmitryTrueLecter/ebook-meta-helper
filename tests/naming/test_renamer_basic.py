from naming.renamer import build_filename
from tests.helpers.book_record_factory import make_record


def test_simple_template():
    r = make_record(title="Book", language="ru")
    name = build_filename(r, "{Title} [{Language}]")
    assert name == "Book [ru]"


def test_authors_and_series():
    r = make_record(
        title="Book",
        authors=["Author"],
        series="Saga",
        series_index=1,
    )
    name = build_filename(r, "{Authors} - {SeriesName} #{SeriesNumber} - {Title}")
    assert name == "Author - Saga #1 - Book"
