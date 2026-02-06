from ai.providers import OpenAIProvider
from models.book import BookRecord


def test_openai_provider_v2_applies_edition_and_original(monkeypatch):
    provider = OpenAIProvider()

    def fake_call(_record):
        return {
            "edition": {
                "title": "Восхождение Хоруса",
                "authors": ["Дэн Абнетт"],
                "series": "Ересь Хоруса",
                "series_index": 1,
                "language": "ru",
            },
            "original": {
                "title": "Horus Rising",
                "authors": ["Dan Abnett"],
                "language": "en",
                "year": 2006,
            },
            "confidence": 0.93,
        }

    monkeypatch.setattr(provider, "_call_openai", fake_call)

    record = BookRecord(
        path="book.fb2",
        original_filename="book.fb2",
        extension="fb2",
        directories=["warhammer"],
    )

    result = provider.enrich(record)

    # Edition
    assert result.title == "Восхождение Хоруса"
    assert result.authors == ["Дэн Абнетт"]
    assert result.series == "Ересь Хоруса"
    assert result.series_index == 1
    assert result.language == "ru"

    # Original
    assert result.original is not None
    assert result.original.title == "Horus Rising"
    assert result.original.authors == ["Dan Abnett"]
    assert result.original.language == "en"
    assert result.original.year == 2006

    # Provenance
    assert result.source == "ai"
    assert result.confidence == 0.93
