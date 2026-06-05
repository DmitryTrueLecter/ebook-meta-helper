"""Tests for the book-metadata prompt builders against the live v2 contract."""

import json

from app.ai.prompt.book_metadata import (
    build_book_metadata_prompt,
    build_system_prompt,
    get_response_format,
)
from app.models.book import BookRecord, OriginalWork


def test_system_prompt_contains_extraction_instructions():
    prompt = build_system_prompt()

    assert "bibliographic metadata extractor" in prompt
    assert "translated" in prompt.lower()
    assert "directory" in prompt.lower()


def test_response_format_declares_json_contract():
    response_format = get_response_format()

    serialized = json.dumps(response_format)
    assert '"edition"' in serialized
    assert '"original"' in serialized
    assert '"confidence"' in serialized
    assert response_format["format"]["type"] == "json_schema"


def test_prompt_contains_file_context():
    record = BookRecord(
        path="x",
        original_filename="Horus_Rising.fb2",
        extension="fb2",
        directories=["warhammer", "heresy"],
        title="Восхождение Хоруса",
        authors=["Дэн Абнетт"],
        language="ru",
        original=OriginalWork(
            title="Horus Rising",
            authors=["Dan Abnett"],
            language="en",
        ),
    )

    prompt = build_book_metadata_prompt(record)

    assert "Horus_Rising.fb2" in prompt
    assert "warhammer / heresy" in prompt
    assert "Восхождение Хоруса" in prompt
    assert "Horus Rising" in prompt


def test_prompt_includes_all_edition_fields():
    record = BookRecord(
        path="x",
        original_filename="test.epub",
        extension="epub",
        directories=[],
        title="Test Title",
        subtitle="Test Subtitle",
        authors=["Author One", "Author Two"],
        series="Test Series",
        series_index=5,
        series_total=10,
        language="en",
        publisher="Test Publisher",
        year=2020,
        isbn10="1234567890",
        isbn13="1234567890123",
        asin="B012345678",
    )

    prompt = build_book_metadata_prompt(record)

    # v2 labels are derived from schema field descriptions (first sentence).
    assert "Test Title" in prompt
    assert "Test Subtitle" in prompt
    assert "Author One, Author Two" in prompt
    assert "Test Series" in prompt
    assert "Test Publisher" in prompt
    assert "1234567890" in prompt
    assert "1234567890123" in prompt
    assert "B012345678" in prompt


def test_prompt_includes_original_fields():
    record = BookRecord(
        path="x",
        original_filename="test.fb2",
        extension="fb2",
        directories=[],
        title="Translated Title",
        language="ru",
        original=OriginalWork(
            title="Original Title",
            authors=["Original Author"],
            language="en",
            year=2015,
        ),
    )

    prompt = build_book_metadata_prompt(record)

    assert "Existing original work metadata:" in prompt
    assert "Original Title" in prompt
    assert "Original Author" in prompt


def test_prompt_with_minimal_metadata():
    record = BookRecord(
        path="x",
        original_filename="unknown.pdf",
        extension="pdf",
        directories=[],
    )

    prompt = build_book_metadata_prompt(record)

    assert "unknown.pdf" in prompt
    # With no metadata there are no "Existing ..." sections.
    assert "Existing edition metadata:" not in prompt
    assert "Existing original work metadata:" not in prompt


def test_prompt_skips_empty_lists():
    record = BookRecord(
        path="x",
        original_filename="test.epub",
        extension="epub",
        directories=[],
        title="Test",
        authors=[],
    )

    prompt = build_book_metadata_prompt(record)

    assert "Test" in prompt
    # The edition authors label must not appear for an empty author list.
    assert "List of authors for this edition" not in prompt
