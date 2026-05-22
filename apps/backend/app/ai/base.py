from abc import ABC, abstractmethod

from app.models.book import BookRecord


class AIProvider(ABC):
    name: str  # "openai", "dummy", etc.

    @abstractmethod
    def enrich(self, record: BookRecord, hint: dict | None = None) -> BookRecord:
        """Return a NEW enriched BookRecord; must not mutate input."""
        raise NotImplementedError
