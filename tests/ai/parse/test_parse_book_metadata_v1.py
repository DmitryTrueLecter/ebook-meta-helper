from ai.parse.book_metadata_v1 import parse_book_metadata_v1
from datetime import date


def test_valid_response():
    """Test parsing valid response with edition, original, and confidence"""
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

    parsed, errors = parse_book_metadata_v1(raw)

    assert not errors
    assert parsed["edition"]["title"] == "Test"
    assert parsed["original"]["language"] == "en"
    assert parsed["confidence"] == 0.8


def test_all_edition_fields():
    """Test parsing all possible edition fields from schema"""
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

    parsed, errors = parse_book_metadata_v1(raw)

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
    assert parsed["edition"]["published"] == date(2020, 5, 15)
    assert parsed["edition"]["year"] == 2020


def test_all_original_fields():
    """Test parsing all possible original work fields"""
    raw = {
        "original": {
            "title": "Original Title",
            "authors": ["Original Author"],
            "language": "en",
            "year": 2015,
        }
    }

    parsed, errors = parse_book_metadata_v1(raw)

    assert not errors
    assert parsed["original"]["title"] == "Original Title"
    assert parsed["original"]["authors"] == ["Original Author"]
    assert parsed["original"]["language"] == "en"
    assert parsed["original"]["year"] == 2015


def test_invalid_types_are_reported():
    """Test that invalid field types generate errors"""
    raw = {
        "edition": {
            "authors": "not-a-list",
            "year": "2000",
        },
        "confidence": 5,
    }

    parsed, errors = parse_book_metadata_v1(raw)

    assert "edition.authors has invalid type" in errors
    assert "edition.year has invalid type" in errors
    # Confidence is 5, which is out of range 0-1
    assert any("out of range" in err for err in errors)


def test_invalid_date_format():
    """Test that invalid ISO date format is reported"""
    raw = {
        "edition": {
            "published": "not-a-date",
        }
    }

    parsed, errors = parse_book_metadata_v1(raw)

    assert any("published" in err and "invalid" in err.lower() for err in errors)


def test_valid_date_parsing():
    """Test that valid ISO dates are parsed correctly"""
    raw = {
        "edition": {
            "published": "2020-12-25",
        }
    }

    parsed, errors = parse_book_metadata_v1(raw)

    assert not errors
    assert parsed["edition"]["published"] == date(2020, 12, 25)


def test_json_string_parsing():
    """Test parsing from JSON string"""
    import json

    raw_dict = {
        "edition": {"title": "Test"},
        "confidence": 0.9,
    }
    raw_json = json.dumps(raw_dict)

    parsed, errors = parse_book_metadata_v1(raw_json)

    assert not errors
    assert parsed["edition"]["title"] == "Test"
    assert parsed["confidence"] == 0.9


def test_invalid_json_string():
    """Test that invalid JSON string is reported"""
    raw = "not valid json{"

    parsed, errors = parse_book_metadata_v1(raw)

    assert errors
    assert "invalid json" in errors[0].lower()


def test_confidence_range_validation():
    """Test confidence range validation (0.0 to 1.0)"""
    # Valid confidence
    parsed, errors = parse_book_metadata_v1({"confidence": 0.5})
    assert not errors
    assert parsed["confidence"] == 0.5

    # Edge cases
    parsed, errors = parse_book_metadata_v1({"confidence": 0.0})
    assert not errors

    parsed, errors = parse_book_metadata_v1({"confidence": 1.0})
    assert not errors

    # Out of range
    parsed, errors = parse_book_metadata_v1({"confidence": 1.5})
    assert any("out of range" in err for err in errors)

    parsed, errors = parse_book_metadata_v1({"confidence": -0.1})
    assert any("out of range" in err for err in errors)


def test_unknown_fields_ignored():
    """Test that unknown fields are silently ignored"""
    raw = {
        "edition": {
            "title": "Test",
            "unknown_field": "should be ignored",
        }
    }

    parsed, errors = parse_book_metadata_v1(raw)

    assert not errors
    assert parsed["edition"]["title"] == "Test"
    assert "unknown_field" not in parsed["edition"]


def test_empty_response():
    """Test parsing empty response"""
    raw = {}

    parsed, errors = parse_book_metadata_v1(raw)

    assert not errors
    assert parsed == {}


def test_partial_response():
    """Test parsing response with only some fields"""
    raw = {
        "edition": {
            "title": "Only Title",
        }
    }

    parsed, errors = parse_book_metadata_v1(raw)

    assert not errors
    assert parsed["edition"]["title"] == "Only Title"
    assert len(parsed["edition"]) == 1
