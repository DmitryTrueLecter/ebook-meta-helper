import os
import json
from copy import deepcopy
from typing import Any, Dict, Optional

from openai import OpenAI

from app.ai.base import AIProvider
from app.ai.parse.book_metadata import parse_book_metadata
from app.ai.prompt.book_metadata import (
    build_book_metadata_prompt,
    build_system_prompt,
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


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None

    def enrich(
        self,
        record: BookRecord,
        directory_hint: Optional[dict] = None,
    ) -> BookRecord:
        result = deepcopy(record)

        try:
            raw = self._call_openai(record, directory_hint)
            parsed, errors = parse_book_metadata(raw)

            result.errors.extend(errors)

            if parsed:
                self._apply(parsed, result)

        except Exception as e:
            result.errors.append(f"openai: {e}")

        return result

    def summarize_directory(self, files: list[BookRecord]) -> dict:
        if not files:
            return empty_summary()

        raw = self._call_openai_for_directory_summary(files)
        return normalize_summary(raw)

    def _call_openai(
        self,
        record: BookRecord,
        directory_hint: Optional[dict] = None,
    ) -> Dict[str, Any]:
        client = self._get_client()
        system_prompt = build_system_prompt()
        user_prompt = build_book_metadata_prompt(record, directory_hint)
        format_prompt = get_response_format()
        print(system_prompt)
        print(user_prompt)

        response = client.responses.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-5.2"),
            reasoning={"effort": "high"},
            instructions=system_prompt,
            input=user_prompt,
            text=format_prompt
        )

        content = response.output_text
        print(content)
        return json.loads(content)

    def _call_openai_for_directory_summary(
        self, files: list[BookRecord]
    ) -> Dict[str, Any]:
        client = self._get_client()
        system_prompt = build_directory_summary_system_prompt()
        user_prompt = build_directory_summary_user_prompt(files)
        format_prompt = get_directory_summary_response_format()

        response = client.responses.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-5.2"),
            reasoning={"effort": "high"},
            instructions=system_prompt,
            input=user_prompt,
            text=format_prompt,
        )

        content = response.output_text
        return json.loads(content)

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
