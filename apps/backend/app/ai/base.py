from abc import ABC, abstractmethod

from app.models.book import BookRecord


class AIProvider(ABC):
    name: str  # "openai", "dummy", etc.

    @abstractmethod
    def enrich(self, record: BookRecord, hint: dict | None = None) -> BookRecord:
        """
        Takes BookRecord and an optional directory-level hint dict.
        Returns NEW BookRecord.
        Must NOT mutate input.
        """
        raise NotImplementedError
