from models.book import BookRecord
from ai.enrich import enrich


def test_dummy_ai_provider_overwrites_metadata():
    record = BookRecord(
        path="book.epub",
        original_filename="book.epub",
        extension="epub",
        directories=["sci-fi"],
        title="Old",
        authors=["Human"],
        source="file",
    )

    result = enrich(record, provider_name="dummy")

    assert record.title == "Old"              # input not mutated
    assert result.title == "AI Title"
    assert result.authors == ["AI Author"]
    assert result.language == "en"
    assert result.source == "ai"
    assert result.confidence == 0.9
