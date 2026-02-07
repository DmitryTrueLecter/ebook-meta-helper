import os
import json
from copy import deepcopy
from typing import Any, Dict, Optional

from openai import OpenAI

from ai.base import AIProvider
from ai.parse.book_metadata_v1 import parse_book_metadata_v1
from ai.prompt.book_metadata_v1 import build_book_metadata_prompt
from models.book import BookRecord, OriginalWork


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None

    def enrich(self, record: BookRecord) -> BookRecord:
        result = deepcopy(record)

        try:
            raw = self._call_openai(record)
            parsed, errors = parse_book_metadata_v1(raw)

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
        prompt = build_book_metadata_prompt(record)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You return only valid JSON.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
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
        edition = data.get("edition", {})

        for field in (
            "title",
            "subtitle",
            "authors",
            "series",
            "series_index",
            "series_total",
            "language",
            "publisher",
            "year",
            "isbn10",
            "isbn13",
            "asin",
        ):
            if field in edition:
                setattr(record, field, edition[field])

        original = data.get("original")
        if isinstance(original, dict):
            record.original = OriginalWork(
                title=original.get("title"),
                authors=original.get("authors", []),
                language=original.get("language"),
                year=original.get("year"),
            )

        if "confidence" in data:
            record.confidence = data["confidence"]

        record.source = "ai"
