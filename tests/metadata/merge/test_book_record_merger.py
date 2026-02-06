from metadata.merge import merge_book_records
from tests.helpers.book_record_factory import make_record


def test_merge_ai_over_file():
    file = make_record(title="Old", source="file")
    ai = make_record(title="New", source="ai")

    result = merge_book_records([file, ai])

    assert result.title == "New"
    assert result.source == "mixed"
