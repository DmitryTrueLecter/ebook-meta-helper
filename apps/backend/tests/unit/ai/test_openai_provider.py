from types import SimpleNamespace
from unittest.mock import MagicMock

from app.ai.base import AIConfigSnapshot
from app.ai.providers import OpenAIProvider
from app.models.book import BookRecord


def _config() -> AIConfigSnapshot:
    return AIConfigSnapshot(
        system_prompt="sys",
        cheap_model="cheap-model",
        expensive_model="expensive-model",
        escalation_threshold=0.7,
        response_format_ref="book_edition_info",
        provider="openai",
        effort="high",
    )


def _record() -> BookRecord:
    return BookRecord(
        path="book.fb2",
        original_filename="book.fb2",
        extension="fb2",
        directories=["warhammer"],
    )


def _mock_client(output_text: str) -> MagicMock:
    client = MagicMock()
    client.responses.create.return_value = SimpleNamespace(output_text=output_text)
    return client


def test_call_openai_nests_format_under_text_format(monkeypatch):
    provider = OpenAIProvider()
    client = _mock_client('{"edition": {}, "original": {}, "confidence": 0.0}')
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    provider._call_openai(_record())

    kwargs = client.responses.create.call_args.kwargs
    text = kwargs["text"]
    assert "type" not in text
    assert text["format"]["type"] == "json_schema"
    assert text["format"]["name"] == "book_edition_info"
    assert "schema" in text["format"]


def test_call_directory_summary_nests_format_under_text_format(monkeypatch):
    provider = OpenAIProvider()
    client = _mock_client('{"confidence": 0.0}')
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    provider._call_openai_for_directory_summary([_record()])

    kwargs = client.responses.create.call_args.kwargs
    text = kwargs["text"]
    assert "type" not in text
    assert text["format"]["type"] == "json_schema"
    assert text["format"]["name"] == "directory_summary"
    assert "schema" in text["format"]


def test_model_default_is_a_real_model(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    provider = OpenAIProvider()
    client = _mock_client('{"confidence": 0.0}')
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    provider._call_openai_for_directory_summary([_record()])

    assert client.responses.create.call_args.kwargs["model"] == "gpt-4o-mini"


def test_openai_provider_v2_applies_edition_and_original(monkeypatch):
    provider = OpenAIProvider()

    def fake_call(_record, _directory_hint=None):
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

    outcome = provider.enrich(record, _config())
    result = outcome.record

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
    assert len(outcome.calls) == 1
    assert outcome.canonical_sequence == 0
