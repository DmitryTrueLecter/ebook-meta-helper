from ai.prompt.book_metadata import build_book_metadata_prompt
from models.book import BookRecord, OriginalWork


def test_prompt_contains_required_sections():
    """Test that prompt includes all basic required sections"""
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

    # Instructions
    assert "ONLY with valid JSON" in prompt
    assert "bibliographic metadata extraction" in prompt

    # File context
    assert "Horus_Rising.fb2" in prompt
    assert "warhammer / heresy" in prompt
    assert "fb2" in prompt

    # JSON contract
    assert '"edition"' in prompt
    assert '"original"' in prompt
    assert '"confidence"' in prompt

    # Existing metadata
    assert "Восхождение Хоруса" in prompt
    assert "Horus Rising" in prompt


def test_prompt_includes_all_edition_fields():
    """Test that prompt correctly shows all edition fields from schema"""
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

    # Check that all fields appear in "Existing edition metadata" section
    assert "Title: Test Title" in prompt
    assert "Subtitle: Test Subtitle" in prompt
    assert "Authors: Author One, Author Two" in prompt
    assert "Series: Test Series" in prompt
    assert "Series number: 5" in prompt
    assert "Series total: 10" in prompt
    assert "Language: en" in prompt
    assert "Publisher: Test Publisher" in prompt
    assert "Published year: 2020" in prompt
    assert "ISBN-10: 1234567890" in prompt
    assert "ISBN-13: 1234567890123" in prompt
    assert "ASIN: B012345678" in prompt


def test_prompt_includes_original_fields():
    """Test that prompt correctly shows all original work fields"""
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

    # Check original work section
    assert "Existing original work metadata:" in prompt
    assert "Original title: Original Title" in prompt
    assert "Original authors: Original Author" in prompt
    assert "Original language: en" in prompt
    assert "Original year: 2015" in prompt


def test_prompt_with_minimal_metadata():
    """Test prompt with only required file info, no metadata"""
    record = BookRecord(
        path="x",
        original_filename="unknown.pdf",
        extension="pdf",
        directories=[],
    )

    prompt = build_book_metadata_prompt(record)

    # Should still have structure
    assert "unknown.pdf" in prompt
    assert "pdf" in prompt
    assert '"edition"' in prompt
    assert '"original"' in prompt

    # Should NOT have metadata sections
    assert "Existing edition metadata:" not in prompt
    assert "Existing original work metadata:" not in prompt


def test_prompt_includes_schema_rules():
    """Test that prompt includes rules from schema"""
    record = BookRecord(
        path="x",
        original_filename="test.epub",
        extension="epub",
        directories=[],
    )

    prompt = build_book_metadata_prompt(record)

    # Check that schema rules are included
    assert "All fields are optional" in prompt
    assert "Edition describes the concrete file" in prompt
    assert "Original describes the original work" in prompt
    assert "translation" in prompt.lower()


def test_prompt_includes_ai_hints():
    """Test that prompt includes AI hints for fields"""
    record = BookRecord(
        path="x",
        original_filename="test.epub",
        extension="epub",
        directories=[],
    )

    prompt = build_book_metadata_prompt(record)

    # Check some AI hints are present in the JSON format description
    assert "title" in prompt.lower()
    assert "string" in prompt.lower()
    assert "array" in prompt.lower()
    assert "integer" in prompt.lower()
    assert "number" in prompt.lower()


def test_prompt_skips_empty_lists():
    """Test that empty author lists are not shown"""
    record = BookRecord(
        path="x",
        original_filename="test.epub",
        extension="epub",
        directories=[],
        title="Test",
        authors=[],  # Empty list
    )

    prompt = build_book_metadata_prompt(record)

    # Should show title but not authors
    assert "Title: Test" in prompt
    assert "Authors:" not in prompt
