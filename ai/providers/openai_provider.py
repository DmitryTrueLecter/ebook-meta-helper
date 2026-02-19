import os
import json
from copy import deepcopy
from typing import Any, Dict, Optional

from openai import OpenAI

from ai.base import AIProvider
from ai.parse.book_metadata import parse_book_metadata
from ai.prompt.book_metadata import build_book_metadata_prompt, build_system_prompt, get_response_format
from ai.contracts.schema_loader import get_edition_fields, get_original_fields
from models.book import BookRecord, OriginalWork


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None

    def enrich(self, record: BookRecord) -> BookRecord:
        result = deepcopy(record)

        try:
            raw = self._call_openai(record)
            parsed, errors = parse_book_metadata(raw)

            result.errors.extend(errors)

            if parsed:
                self._apply(parsed, result)

        except Exception as e:
            result.errors.append(f"openai: {e}")

        return result

    # =====================
    # Transport
    # =====================

    def _call_openai(self, record: BookRecord) -> Dict[str, Any]:
        client = self._get_client()
        system_prompt = build_system_prompt()
        user_prompt = build_book_metadata_prompt(record)
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

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is not set")
            self._client = OpenAI(api_key=api_key)
        return self._client

    # =====================
    # Apply parsed data
    # =====================

    def _apply(self, data: Dict[str, Any], record: BookRecord) -> None:
        """Apply parsed data to BookRecord using schema field definitions"""
        edition = data.get("edition", {})

        # Apply edition fields dynamically from schema
        edition_fields = get_edition_fields()
        for field_name in edition_fields.keys():
            if field_name in edition:
                setattr(record, field_name, edition[field_name])

        # Apply original fields dynamically from schema
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