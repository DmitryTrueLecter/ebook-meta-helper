import os
import json
from copy import deepcopy
from typing import Any, Dict, Optional

from openai import OpenAI, OpenAIError

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
            data = self._call_openai(record)

            parsed, errors = parse_book_metadata_v1(data)
            result.errors.extend(errors)

            if parsed:
                self._apply(parsed, result)

        except Exception as e:
            result.errors.append(f"openai: {e}")

        return result

    # =====================
    # Separated for testing
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
                    "content": (
                        "You are a bibliographic metadata extraction engine. "
                        "You must return only valid JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format={"type": "json_object"},
        )

        raw_text = response.choices[0].message.content
        return json.loads(raw_text)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is not set")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def _apply(self, data: Dict[str, Any], record: BookRecord) -> None:
        edition = data.get("edition", {})
        for key in (
            "title",
            "authors",
            "series",
            "series_index",
            "language",
            "year",
        ):
            if key in edition:
                setattr(record, key, edition[key])

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
