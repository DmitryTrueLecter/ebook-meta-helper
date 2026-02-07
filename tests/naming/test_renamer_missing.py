import pytest

from naming.renamer import build_filename, RenameError
from tests.helpers.book_record_factory import make_record


def test_missing_skip():
    r = make_record(title="Book")
    name = build_filename(r, "{Title} - {SeriesName}", missing="skip")
    assert name == "Book"


def test_missing_empty():
    r = make_record(title="Book")
    name = build_filename(r, "{Title}{SeriesName}", missing="empty")
    assert name == "Book"


def test_missing_error():
    r = make_record(title="Book")
    with pytest.raises(RenameError):
        build_filename(r, "{SeriesName}", missing="error")
