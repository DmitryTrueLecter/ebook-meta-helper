import json

from ai.base import AIProvider
from models.book import BookRecord


class OpenAIProvider(AIProvider):
    name = "openai"

    def enrich(self, record: BookRecord) -> BookRecord:
        try:
            response = self._call_openai(record)
            return self._apply_response(record, response)
        except Exception as e:
            record.errors.append(f"openai: {e}")
            return record

    def _call_openai(self, record: BookRecord) -> dict:
        raise NotImplementedError("Network call not implemented yet")

    def _apply_response(self, record: BookRecord, data: dict) -> BookRecord:
        record.title = data.get("title", record.title)
        record.authors = data.get("authors", record.authors)
        record.series = data.get("series", record.series)
        record.series_index = data.get("series_index", record.series_index)
        record.language = data.get("language", record.language)
        record.year = data.get("year", record.year)

        record.source = "ai"
        record.confidence = data.get("confidence")

        return record
