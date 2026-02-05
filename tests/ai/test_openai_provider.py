from ai.providers.openai_provider import OpenAIProvider
from models.book import BookRecord


def test_openai_provider_applies_metadata(monkeypatch):
    provider = OpenAIProvider()

    def fake_call(_record):
        return {
            "title": "AI Book",
            "authors": ["AI Author"],
            "confidence": 0.9,
        }

    monkeypatch.setattr(provider, "_call_openai", fake_call)

    record = BookRecord(
        path="book.epub",
        original_filename="book.epub",
        extension="epub",
        directories=[]
    )

    result = provider.enrich(record)

    assert result.title == "AI Book"
    assert result.authors == ["AI Author"]
    assert result.source == "ai"
    assert result.confidence == 0.9
