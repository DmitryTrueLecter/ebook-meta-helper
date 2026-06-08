"""Unit tests for AIProvider.summarize_directory and directory-hint prompt integration."""

import pytest

from app.ai.base import AIConfigSnapshot
from app.ai.providers.dummy import DummyAIProvider
from app.ai.providers.openai_provider import OpenAIProvider, _OpenAICall
from app.ai.prompt.book_metadata import build_book_metadata_prompt
from app.ai.prompt.directory_summary import (
    SUMMARY_KEYS,
    build_directory_summary_system_prompt,
    build_directory_summary_user_prompt,
    empty_summary,
    format_directory_hint_for_book_prompt,
    get_directory_summary_response_format,
    normalize_summary,
)
from app.models.book import BookRecord


def _book(filename: str, directories: list[str]) -> BookRecord:
    return BookRecord(
        path=f"{'/'.join(directories)}/{filename}",
        original_filename=filename,
        extension=filename.rsplit(".", 1)[-1],
        directories=directories,
    )


def _config() -> AIConfigSnapshot:
    return AIConfigSnapshot(
        system_prompt="sys",
        cheap_model="cheap-model",
        expensive_model="expensive-model",
        escalation_threshold=0.7,
        response_format_ref="directory_summary",
        provider="openai",
        effort="high",
    )


def _summary_call(parsed: dict) -> _OpenAICall:
    return _OpenAICall(
        parsed=parsed,
        system_prompt="sys",
        user_prompt="usr",
        raw_response="{}",
        prompt_tokens=None,
        completion_tokens=None,
        duration_ms=0,
    )


class TestDummySummarizeDirectory:
    def test_returns_canonical_shape(self):
        files = [_book("a.fb2", ["warhammer", "heresy"])]
        summary = DummyAIProvider().summarize_directory(files, _config())
        assert set(summary.keys()) == set(SUMMARY_KEYS)

    def test_is_deterministic_for_same_input(self):
        files = [_book("a.fb2", ["scifi", "asimov"]), _book("b.fb2", ["scifi", "asimov"])]
        first = DummyAIProvider().summarize_directory(files, _config())
        second = DummyAIProvider().summarize_directory(files, _config())
        assert first == second

    def test_series_name_uses_common_directory_basename(self):
        files = [
            _book("a.fb2", ["scifi", "asimov", "foundation"]),
            _book("b.fb2", ["scifi", "asimov", "foundation"]),
        ]
        summary = DummyAIProvider().summarize_directory(files, _config())
        assert summary["series_name"] == "foundation"
        assert summary["confidence"] == 0.5

    def test_no_common_directory_yields_null_series(self):
        files = [
            _book("a.fb2", ["scifi", "asimov"]),
            _book("b.fb2", ["fantasy", "tolkien"]),
        ]
        summary = DummyAIProvider().summarize_directory(files, _config())
        assert summary["series_name"] is None
        assert summary["confidence"] == 0.0

    def test_empty_file_list_returns_empty_summary(self):
        summary = DummyAIProvider().summarize_directory([], _config())
        assert summary["series_name"] is None
        assert summary["tags"] == []
        assert summary["confidence"] == 0.0

    def test_does_not_call_any_api(self, monkeypatch):
        # If the dummy ever reached for OpenAI, this would explode.
        monkeypatch.setenv("OPENAI_API_KEY", "")
        files = [_book("a.fb2", ["x"])]
        # Should not raise even with no key configured.
        DummyAIProvider().summarize_directory(files, _config())


class TestOpenAISummarizeDirectory:
    def test_normalizes_well_formed_response(self, monkeypatch):
        provider = OpenAIProvider()

        def fake_call(_files, _config):
            return _summary_call(
                {
                    "series_name": "Horus Heresy",
                    "universe": "Warhammer 40k",
                    "genre": "military sci-fi",
                    "tags": ["warhammer 40k", "space marines"],
                    "language": "en",
                    "confidence": 0.87,
                    "notes": "Numbered sequence, single author cluster.",
                }
            )

        monkeypatch.setattr(provider, "_call_openai_for_directory_summary", fake_call)

        files = [_book("01.fb2", ["wh40k", "heresy"])]
        summary = provider.summarize_directory(files, _config())

        assert summary["series_name"] == "Horus Heresy"
        assert summary["universe"] == "Warhammer 40k"
        assert summary["genre"] == "military sci-fi"
        assert summary["tags"] == ["warhammer 40k", "space marines"]
        assert summary["language"] == "en"
        assert summary["confidence"] == pytest.approx(0.87)
        assert summary["notes"] == "Numbered sequence, single author cluster."

    def test_clamps_confidence_above_one(self, monkeypatch):
        provider = OpenAIProvider()
        monkeypatch.setattr(
            provider,
            "_call_openai_for_directory_summary",
            lambda _files, _config: _summary_call({"confidence": 1.5, "tags": []}),
        )
        summary = provider.summarize_directory([_book("a.fb2", ["x"])], _config())
        assert summary["confidence"] == 1.0

    def test_drops_unexpected_fields(self, monkeypatch):
        provider = OpenAIProvider()
        monkeypatch.setattr(
            provider,
            "_call_openai_for_directory_summary",
            lambda _files, _config: _summary_call(
                {
                    "series_name": "S",
                    "rogue_key": "should not appear",
                    "tags": ["t"],
                }
            ),
        )
        summary = provider.summarize_directory([_book("a.fb2", ["x"])], _config())
        assert "rogue_key" not in summary
        assert set(summary.keys()) == set(SUMMARY_KEYS)

    def test_empty_string_collapses_to_null(self, monkeypatch):
        provider = OpenAIProvider()
        monkeypatch.setattr(
            provider,
            "_call_openai_for_directory_summary",
            lambda _files, _config: _summary_call(
                {"series_name": "", "tags": ["", "t"], "notes": ""}
            ),
        )
        summary = provider.summarize_directory([_book("a.fb2", ["x"])], _config())
        assert summary["series_name"] is None
        assert summary["tags"] == ["t"]
        assert summary["notes"] is None

    def test_propagates_transport_error(self, monkeypatch):
        provider = OpenAIProvider()

        def boom(_files, _config):
            raise RuntimeError("upstream 500")

        monkeypatch.setattr(provider, "_call_openai_for_directory_summary", boom)
        with pytest.raises(RuntimeError, match="upstream 500"):
            provider.summarize_directory([_book("a.fb2", ["x"])], _config())

    def test_empty_file_list_short_circuits_without_api_call(self, monkeypatch):
        provider = OpenAIProvider()

        def boom(_files, _config):  # pragma: no cover — must not be called
            raise AssertionError("API should not be touched for empty input")

        monkeypatch.setattr(provider, "_call_openai_for_directory_summary", boom)
        summary = provider.summarize_directory([], _config())
        assert summary == empty_summary()


class TestDirectorySummaryPrompt:
    def test_system_prompt_describes_role(self):
        system = build_directory_summary_system_prompt()
        assert "collection" in system.lower()

    def test_user_prompt_lists_filenames(self):
        files = [
            _book("01.fb2", ["wh40k", "heresy"]),
            _book("02.fb2", ["wh40k", "heresy"]),
        ]
        prompt = build_directory_summary_user_prompt(files)
        assert "01.fb2" in prompt
        assert "02.fb2" in prompt
        assert "File count: 2" in prompt
        assert "wh40k / heresy" in prompt

    def test_user_prompt_handles_mixed_directories(self):
        files = [
            _book("a.fb2", ["scifi", "asimov"]),
            _book("b.fb2", ["fantasy", "tolkien"]),
        ]
        prompt = build_directory_summary_user_prompt(files)
        # No common prefix → no directory line, only filenames
        assert "Directory path:" not in prompt
        assert "a.fb2" in prompt
        assert "b.fb2" in prompt

    def test_response_format_required_lists_all_keys(self):
        fmt = get_directory_summary_response_format()
        required = fmt["schema"]["required"]
        assert set(required) == set(SUMMARY_KEYS)
        assert fmt["schema"]["additionalProperties"] is False


class TestNormalizeSummary:
    def test_non_dict_input_returns_empty(self):
        assert normalize_summary(None) == empty_summary()
        assert normalize_summary("string") == empty_summary()
        assert normalize_summary([]) == empty_summary()

    def test_missing_keys_get_defaults(self):
        result = normalize_summary({"series_name": "S"})
        assert result["series_name"] == "S"
        assert result["universe"] is None
        assert result["tags"] == []
        assert result["confidence"] == 0.0

    def test_tags_filtered_to_non_empty_strings(self):
        result = normalize_summary({"tags": ["a", "", None, 42, "b"]})
        assert result["tags"] == ["a", "b"]

    def test_confidence_below_zero_clamped(self):
        assert normalize_summary({"confidence": -0.5})["confidence"] == 0.0

    def test_non_numeric_confidence_falls_back_to_default(self):
        assert normalize_summary({"confidence": "high"})["confidence"] == 0.0


class TestFormatDirectoryHintForBookPrompt:
    def test_none_hint_returns_empty_string(self):
        assert format_directory_hint_for_book_prompt(None) == ""

    def test_empty_summary_returns_empty_string(self):
        assert format_directory_hint_for_book_prompt(empty_summary()) == ""

    def test_renders_present_fields_with_labels(self):
        hint = {
            "series_name": "Horus Heresy",
            "universe": "Warhammer 40k",
            "genre": "military sci-fi",
            "tags": ["space marines", "imperium"],
            "language": "en",
            "confidence": 0.9,
            "notes": "anything",
        }
        block = format_directory_hint_for_book_prompt(hint)
        assert "Context: This book is from a collection summarized as:" in block
        assert "Series: Horus Heresy" in block
        assert "Universe: Warhammer 40k" in block
        assert "Genre: military sci-fi" in block
        assert "Tags: space marines, imperium" in block
        assert "Language: en" in block

    def test_empty_tag_list_is_omitted(self):
        hint = empty_summary()
        hint["series_name"] = "S"
        # tags defaults to [] in empty_summary
        block = format_directory_hint_for_book_prompt(hint)
        assert "Series: S" in block
        assert "Tags:" not in block


class TestBookMetadataPromptWithDirectoryHint:
    def _record(self) -> BookRecord:
        return BookRecord(
            path="x",
            original_filename="Horus_Rising.fb2",
            extension="fb2",
            directories=["warhammer", "heresy"],
        )

    def test_without_hint_no_context_block(self):
        prompt = build_book_metadata_prompt(self._record(), directory_hint=None)
        assert "Context: This book is from a collection summarized as:" not in prompt

    def test_with_hint_renders_context_block_before_file_context(self):
        hint = empty_summary()
        hint["series_name"] = "Horus Heresy"
        hint["universe"] = "Warhammer 40k"
        prompt = build_book_metadata_prompt(self._record(), directory_hint=hint)

        # Context block present
        assert "Context: This book is from a collection summarized as:" in prompt
        assert "Series: Horus Heresy" in prompt
        assert "Universe: Warhammer 40k" in prompt

        # Ordering: context block comes before file context
        context_idx = prompt.index("Context: This book is from a collection")
        file_idx = prompt.index("Known file context:")
        assert context_idx < file_idx

    def test_empty_hint_does_not_add_context_block(self):
        # All fields null/empty → no block emitted
        prompt = build_book_metadata_prompt(self._record(), directory_hint=empty_summary())
        assert "Context: This book is from a collection summarized as:" not in prompt
