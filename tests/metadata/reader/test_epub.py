import pytest
from unittest.mock import patch, MagicMock
from models.book import BookRecord
from metadata.reader.registry import read_metadata

def test_epub_reader_basic(monkeypatch):
    record = BookRecord(
        path="dummy.epub",
        original_filename="dummy.epub",
        extension="epub",
        directories=[]
    )

    fake_book = MagicMock()
    fake_book.get_metadata.side_effect = lambda namespace, tag: {
        ("DC", "title"): [("EPUB Book", {})],
        ("DC", "creator"): [("Alice", {}), ("Bob", {})],
        ("DC", "language"): [("en", {})]
    }.get((namespace, tag), [])

    with patch("merge.reader.epub.epub.read_epub", return_value=fake_book):
        record = read_metadata(record)

    assert record.title == "EPUB Book"
    assert record.authors == ["Alice", "Bob"]
    assert record.language == "en"
