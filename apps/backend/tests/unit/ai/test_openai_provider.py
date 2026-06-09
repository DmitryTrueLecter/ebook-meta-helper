from types import SimpleNamespace
from unittest.mock import MagicMock

from app.ai.base import AIConfigSnapshot
from app.ai.providers import OpenAIProvider
from app.ai.providers.openai_provider import _OpenAICall
from app.models.book import BookRecord


def _config(effort: str | None = "high") -> AIConfigSnapshot:
    return AIConfigSnapshot(
        system_prompt="sys",
        cheap_model="cheap-model",
        expensive_model="expensive-model",
        escalation_threshold=0.7,
        response_format_ref="book_edition_info",
        provider="openai",
        effort=effort,
    )


def _record() -> BookRecord:
    return BookRecord(
        path="book.fb2",
        original_filename="book.fb2",
        extension="fb2",
        directories=["warhammer"],
    )


def _mock_client(output_text: str, usage=None) -> MagicMock:
    client = MagicMock()
    client.responses.create.return_value = SimpleNamespace(
        output_text=output_text, usage=usage
    )
    return client


def test_call_openai_nests_format_under_text_format(monkeypatch):
    provider = OpenAIProvider()
    client = _mock_client('{"edition": {}, "original": {}, "confidence": 0.0}')
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    provider._call_openai(_record(), _config())

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

    provider._call_openai_for_directory_summary([_record()], _config())

    kwargs = client.responses.create.call_args.kwargs
    text = kwargs["text"]
    assert "type" not in text
    assert text["format"]["type"] == "json_schema"
    assert text["format"]["name"] == "directory_summary"
    assert "schema" in text["format"]


def test_model_comes_from_config_not_env(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "env-should-be-ignored")
    provider = OpenAIProvider()
    client = _mock_client('{"confidence": 0.0}')
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    provider._call_openai_for_directory_summary([_record()], _config())

    assert client.responses.create.call_args.kwargs["model"] == "cheap-model"


def test_effort_comes_from_config(monkeypatch):
    provider = OpenAIProvider()
    client = _mock_client('{"confidence": 0.0}')
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    provider._call_openai(_record(), _config(effort="low"))

    assert client.responses.create.call_args.kwargs["reasoning"] == {"effort": "low"}


def test_reasoning_omitted_when_effort_is_none(monkeypatch):
    provider = OpenAIProvider()
    client = _mock_client('{"confidence": 0.0}')
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    provider._call_openai(_record(), _config(effort=None))

    assert "reasoning" not in client.responses.create.call_args.kwargs


def test_call_captures_token_usage_and_raw_response(monkeypatch):
    provider = OpenAIProvider()
    usage = SimpleNamespace(input_tokens=11, output_tokens=22)
    client = _mock_client('{"confidence": 0.0}', usage=usage)
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    call = provider._call_openai(_record(), _config())

    assert call.prompt_tokens == 11
    assert call.completion_tokens == 22
    assert call.raw_response == '{"confidence": 0.0}'
    assert call.system_prompt == "sys"


def test_call_tokens_none_when_usage_absent(monkeypatch):
    provider = OpenAIProvider()
    client = _mock_client('{"confidence": 0.0}', usage=None)
    monkeypatch.setattr(provider, "_get_client", lambda: client)

    call = provider._call_openai(_record(), _config())

    assert call.prompt_tokens is None
    assert call.completion_tokens is None


def _fake_call(parsed: dict) -> _OpenAICall:
    return _OpenAICall(
        parsed=parsed,
        system_prompt="sys",
        user_prompt="usr",
        raw_response="{}",
        prompt_tokens=7,
        completion_tokens=9,
        duration_ms=5,
    )


def test_openai_provider_v2_applies_edition_and_original(monkeypatch):
    provider = OpenAIProvider()

    def fake_call(_record, _config, _directory_hint=None):
        return _fake_call(
            {
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
        )

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


def test_enrich_call_record_reflects_actual_call_values(monkeypatch):
    provider = OpenAIProvider()
    monkeypatch.setattr(
        provider,
        "_call_openai",
        lambda _record, _config, _directory_hint=None: _fake_call({"confidence": 0.5}),
    )

    outcome = provider.enrich(_record(), _config(effort="low"))
    call = outcome.calls[0]

    assert call.model == "cheap-model"
    assert call.effort == "low"
    assert call.prompt_tokens == 7
    assert call.completion_tokens == 9
    assert call.duration_ms == 5
    assert call.tier == "cheap"
    assert call.sequence == 0


def test_enrich_records_transport_failure_without_propagating(monkeypatch):
    provider = OpenAIProvider()

    def boom(_record, _config, _directory_hint=None):
        raise ConnectionError("upstream 500")

    monkeypatch.setattr(provider, "_call_openai", boom)

    outcome = provider.enrich(_record(), _config())
    call = outcome.calls[0]

    assert "openai: upstream 500" in outcome.record.errors
    assert call.parse_errors == ["openai: upstream 500"]
    assert call.model == "cheap-model"
    assert call.duration_ms == 0
    assert call.prompt_tokens is None
