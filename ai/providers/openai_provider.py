from typing import Dict, Any

from ai.base import AIProvider
from models.book import BookRecord, OriginalWork


class OpenAIProvider(AIProvider):
    name = "openai"

    def enrich(self, record: BookRecord) -> BookRecord:
        try:
            data = self._call_openai(record)
            return self._apply_response(record, data)
        except Exception as e:
            record.errors.append(f"openai: {e}")
            return record

    def _call_openai(self, record: BookRecord) -> Dict[str, Any]:
        """
        Network call placeholder.
        Must return dict compatible with book_metadata.v2.json
        """
        raise NotImplementedError("OpenAI network call not implemented")

    def _apply_response(self, record: BookRecord, data: Dict[str, Any]) -> BookRecord:
        # --- Edition (this file) ---
        edition = data.get("edition", {})
        if isinstance(edition, dict):
            for field in (
                "title",
                "authors",
                "series",
                "series_index",
                "language",
                "year",
            ):
                if field in edition:
                    setattr(record, field, edition[field])

        # --- Original work ---
        original = data.get("original")
        if isinstance(original, dict):
            record.original = OriginalWork(
                title=original.get("title"),
                authors=original.get("authors", []),
                language=original.get("language"),
                year=original.get("year"),
            )

        # --- Provenance ---
        record.source = "ai"
        record.confidence = data.get("confidence")

        return record
