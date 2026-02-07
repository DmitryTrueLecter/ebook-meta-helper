from naming.placeholders import PLACEHOLDERS
from tests.helpers.book_record_factory import make_record


def test_title_placeholder():
    r = make_record(title="Test")
    assert PLACEHOLDERS["Title"](r) == "Test"


def test_authors_placeholder():
    r = make_record(authors=["A", "B"])
    assert PLACEHOLDERS["Authors"](r) == "A, B"


def test_missing_placeholder_returns_none():
    r = make_record()
    assert PLACEHOLDERS["Publisher"](r) is None
