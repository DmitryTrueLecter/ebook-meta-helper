from typing import Optional

from app.ai.base import AIProvider
from app.models.book import BookRecord


class DummyAIProvider(AIProvider):
    name = "dummy"

    def enrich(
        self,
        record: BookRecord,
        directory_hint: Optional[dict] = None,
    ) -> BookRecord:
        record.title = "AI Title"
        record.authors = ["AI Author"]
        record.language = "en"

        record.source = "ai"
        record.confidence = 0.9

        return record

    def summarize_directory(self, files: list[BookRecord]) -> dict:
        """Deterministic fake summary derived from the longest common
        directory prefix. Used in tests; performs no API calls."""
        series_name = _common_directory_basename(files)
        return {
            "series_name": series_name,
            "universe": None,
            "genre": None,
            "tags": [],
            "language": None,
            "confidence": 0.5 if series_name else 0.0,
            "notes": None,
        }


def _common_directory_basename(files: list[BookRecord]) -> Optional[str]:
    if not files:
        return None

    common = list(files[0].directories)
    for record in files[1:]:
        new_common: list[str] = []
        for left, right in zip(common, record.directories):
            if left == right:
                new_common.append(left)
            else:
                break
        common = new_common
        if not common:
            return None

    return common[-1] if common else None
