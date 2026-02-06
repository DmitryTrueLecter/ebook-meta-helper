from ai.parse.book_metadata_v1 import parse_book_metadata_v1


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

    parsed, errors = parse_book_metadata_v1(raw)

    assert not errors
    assert parsed["edition"]["title"] == "Test"
    assert parsed["original"]["language"] == "en"
    assert parsed["confidence"] == 0.8


def test_invalid_types_are_reported():
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
    assert "confidence out of range 0..1" in errors
