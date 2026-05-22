from abc import ABC, abstractmethod
from typing import Optional

from app.models.book import BookRecord


class AIProvider(ABC):
    name: str  # "openai", "dummy", etc.

    @abstractmethod
    def enrich(
        self,
        record: BookRecord,
        directory_hint: Optional[dict] = None,
    ) -> BookRecord:
        """Return a NEW BookRecord; must not mutate input."""
        raise NotImplementedError

    @abstractmethod
    def summarize_directory(self, files: list[BookRecord]) -> dict:
        """Collapse a directory of files into the SUMMARY_KEYS-shaped hint dict."""
        raise NotImplementedError
