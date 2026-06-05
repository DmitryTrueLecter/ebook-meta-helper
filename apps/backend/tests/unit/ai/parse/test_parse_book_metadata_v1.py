"""Tests for parse_book_metadata against the live v2 schema contract."""

from app.ai.parse.book_metadata import parse_book_metadata


def test_valid_response():
    raw = {
        "edition": {
            "title": "Test",
            "authors": ["A"],
            "series_index": 1,
        },
        "original": {
            "title": "Original",
            "language": "en",
        },
        "confidence": 0.8,
    }

    parsed, errors = parse_book_metadata(raw)

    assert not errors
    assert parsed["edition"]["title"] == "Test"
    assert parsed["original"]["language"] == "en"
    assert parsed["confidence"] == 0.8


def test_all_edition_fields():
    raw = {
        "edition": {
            "title": "Test Title",
            "subtitle": "Test Subtitle",
            "authors": ["Author One", "Author Two"],
            "series": "Test Series",
            "series_index": 5,
            "series_total": 10,
            "language": "en",
            "publisher": "Test Publisher",
            "isbn10": "1234567890",
            "isbn13": "1234567890123",
            "asin": "B012345678",
            "published": "2020-05-15",
            "year": 2020,
        }
    }

    parsed, errors = parse_book_metadata(raw)

    assert not errors
    assert parsed["edition"]["title"] == "Test Title"
    assert parsed["edition"]["subtitle"] == "Test Subtitle"
    assert parsed["edition"]["authors"] == ["Author One", "Author Two"]
    assert parsed["edition"]["series"] == "Test Series"
    assert parsed["edition"]["series_index"] == 5
    assert parsed["edition"]["series_total"] == 10
    assert parsed["edition"]["language"] == "en"
    assert parsed["edition"]["publisher"] == "Test Publisher"
    assert parsed["edition"]["isbn10"] == "1234567890"
    assert parsed["edition"]["isbn13"] == "1234567890123"
    assert parsed["edition"]["asin"] == "B012345678"
    # v2 surfaces `published` as an ISO date string (no date() coercion).
    assert parsed["edition"]["published"] == "2020-05-15"
    assert parsed["edition"]["year"] == 2020


def test_all_original_fields():
    raw = {
        "original": {
            "title": "Original Title",
            "authors": ["Original Author"],
            "language": "en",
            "year": 2015,
        }
    }

    parsed, errors = parse_book_metadata(raw)

    assert not errors
    assert parsed["original"]["title"] == "Original Title"
    assert parsed["original"]["authors"] == ["Original Author"]
    assert parsed["original"]["language"] == "en"
    assert parsed["original"]["year"] == 2015


def test_invalid_types_are_reported():
    raw = {
        "edition": {
            "authors": "not-a-list",
            "year": "2000",
        },
    }

    parsed, errors = parse_book_metadata(raw)

    assert "edition.authors has invalid type" in errors
    assert "edition.year has invalid type" in errors


def test_invalid_date_format():
    raw = {
        "edition": {
            "published": "not-a-date",
        }
    }

    parsed, errors = parse_book_metadata(raw)

    assert any("published" in err and "invalid" in err.lower() for err in errors)


def test_valid_date_passes_through_as_string():
    raw = {
        "edition": {
            "published": "2020-12-25",
        }
    }

    parsed, errors = parse_book_metadata(raw)

    assert not errors
    # v2 keeps `published` as the raw ISO string; no datetime.date coercion.
    assert parsed["edition"]["published"] == "2020-12-25"


def test_json_string_parsing():
    import json

    raw_dict = {
        "edition": {"title": "Test"},
        "confidence": 0.9,
    }
    raw_json = json.dumps(raw_dict)

    parsed, errors = parse_book_metadata(raw_json)

    assert not errors
    assert parsed["edition"]["title"] == "Test"
    assert parsed["confidence"] == 0.9


def test_invalid_json_string():
    raw = "not valid json{"

    parsed, errors = parse_book_metadata(raw)

    assert errors
    assert "invalid json" in errors[0].lower()


def test_confidence_is_coerced_to_float():
    parsed, errors = parse_book_metadata({"confidence": 0.5})
    assert not errors
    assert parsed["confidence"] == 0.5

    parsed, errors = parse_book_metadata({"confidence": 0.0})
    assert not errors
    assert parsed["confidence"] == 0.0

    parsed, errors = parse_book_metadata({"confidence": 1.0})
    assert not errors
    assert parsed["confidence"] == 1.0


def test_non_numeric_confidence_is_reported():
    parsed, errors = parse_book_metadata({"confidence": "high"})
    assert any("confidence" in err for err in errors)


def test_unknown_fields_ignored():
    raw = {
        "edition": {
            "title": "Test",
            "unknown_field": "should be ignored",
        }
    }

    parsed, errors = parse_book_metadata(raw)

    assert not errors
    assert parsed["edition"]["title"] == "Test"
    assert "unknown_field" not in parsed["edition"]


def test_empty_response():
    raw = {}

    parsed, errors = parse_book_metadata(raw)

    assert not errors
    assert parsed == {}


def test_partial_response():
    raw = {
        "edition": {
            "title": "Only Title",
        }
    }

    parsed, errors = parse_book_metadata(raw)

    assert not errors
    assert parsed["edition"]["title"] == "Only Title"
    assert len(parsed["edition"]) == 1
