import os
import json
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Optional

from openai import OpenAI

from app.ai.base import AICallRecord, AIConfigSnapshot, AIProvider, EnrichOutcome
from app.ai.parse.book_metadata import parse_book_metadata
from app.ai.prompt.book_metadata import (
    build_book_metadata_prompt,
    get_response_format,
)
from app.ai.prompt.directory_summary import (
    build_directory_summary_system_prompt,
    build_directory_summary_user_prompt,
    empty_summary,
    get_directory_summary_response_format,
    normalize_summary,
)
from app.ai.contracts.schema_loader import get_edition_fields, get_original_fields
from app.models.book import BookRecord, OriginalWork


@dataclass(frozen=True)
class _OpenAICall:
    parsed: Dict[str, Any]
    system_prompt: str
    user_prompt: str
    raw_response: str
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    duration_ms: int


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None

    def enrich(
        self,
        record: BookRecord,
        config: AIConfigSnapshot,
        directory_hint: Optional[dict] = None,
    ) -> EnrichOutcome:
        result = deepcopy(record)
        call_errors: list[str] = []
        call: Optional[_OpenAICall] = None

        try:
            call = self._call_openai(record, config, directory_hint)
            parsed, errors = parse_book_metadata(call.parsed)
            call_errors = errors
            result.errors.extend(errors)
            if parsed:
                self._apply(parsed, result)
        except Exception as e:
            message = f"openai: {e}"
            call_errors = [message]
            result.errors.append(message)

        record_of_call = AICallRecord(
            system_prompt=call.system_prompt if call else config.system_prompt,
            user_prompt=call.user_prompt if call else "",
            raw_response=call.raw_response if call else "",
            model=config.cheap_model,
            response_format_ref=config.response_format_ref,
            duration_ms=call.duration_ms if call else 0,
            tier="cheap",
            sequence=0,
            effort=config.effort,
            prompt_tokens=call.prompt_tokens if call else None,
            completion_tokens=call.completion_tokens if call else None,
            confidence=result.confidence,
            parse_errors=call_errors,
        )
        return EnrichOutcome(record=result, calls=[record_of_call], canonical_sequence=0)

    def summarize_directory(
        self, files: list[BookRecord], config: AIConfigSnapshot
    ) -> dict:
        if not files:
            return empty_summary()

        call = self._call_openai_for_directory_summary(files, config)
        return normalize_summary(call.parsed)

    def _call_openai(
        self,
        record: BookRecord,
        config: AIConfigSnapshot,
        directory_hint: Optional[dict] = None,
    ) -> _OpenAICall:
        return self._create_response(
            system_prompt=config.system_prompt,
            user_prompt=build_book_metadata_prompt(record, directory_hint),
            response_format=get_response_format(),
            config=config,
        )

    def _call_openai_for_directory_summary(
        self, files: list[BookRecord], config: AIConfigSnapshot
    ) -> _OpenAICall:
        return self._create_response(
            system_prompt=build_directory_summary_system_prompt(),
            user_prompt=build_directory_summary_user_prompt(files),
            response_format=get_directory_summary_response_format(),
            config=config,
        )

    def _create_response(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict,
        config: AIConfigSnapshot,
    ) -> _OpenAICall:
        client = self._get_client()
        request: Dict[str, Any] = {
            "model": config.cheap_model,
            "instructions": system_prompt,
            "input": user_prompt,
            "text": {"format": response_format},
        }
        if config.effort is not None:
            request["reasoning"] = {"effort": config.effort}

        started = time.monotonic()
        response = client.responses.create(**request)
        duration_ms = int((time.monotonic() - started) * 1000)

        content = response.output_text
        prompt_tokens, completion_tokens = _extract_token_usage(response)
        return _OpenAICall(
            parsed=json.loads(content),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_response=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
        )

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is not set")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def _apply(self, data: Dict[str, Any], record: BookRecord) -> None:
        """Apply parsed data to BookRecord using schema field definitions."""
        edition = data.get("edition", {})

        edition_fields = get_edition_fields()
        for field_name in edition_fields.keys():
            if field_name in edition:
                setattr(record, field_name, edition[field_name])

        original = data.get("original")
        if isinstance(original, dict):
            original_fields = get_original_fields()
            original_kwargs = {}
            for field_name in original_fields.keys():
                if field_name in original:
                    original_kwargs[field_name] = original[field_name]

            if original_kwargs:
                record.original = OriginalWork(**original_kwargs)

        if "confidence" in data:
            record.confidence = data["confidence"]

        record.source = "ai"


def _extract_token_usage(response: Any) -> tuple[Optional[int], Optional[int]]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None, None
    return getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None)
