from ai.providers.dummy import DummyAIProvider
from models.book import BookRecord


def test_dummy_ai_provider_v2():
    provider = DummyAIProvider()

    record = BookRecord(
        path="book.epub",
        original_filename="book.epub",
        extension="epub",
        directories=["sci-fi"],
        title="Old Title",
        authors=["Human"],
        language="ru",
    )

    result = provider.enrich(record)

    # Edition
    assert result.title == "Dummy Edition Title"
    assert result.authors == ["Dummy Author"]
    assert result.series == "Dummy Series"
    assert result.series_index == 1
    assert result.language == "ru"

    # Original
    assert result.original is not None
    assert result.original.title == "Dummy Original Title"
    assert result.original.language == "en"

    # Provenance
    assert result.source == "ai"
    assert result.confidence == 1.0
