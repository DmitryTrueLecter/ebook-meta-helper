from abc import ABC, abstractmethod
from models.book import BookRecord


class AIProvider(ABC):
    name: str  # "openai", "dummy", etc.

    @abstractmethod
    def enrich(self, record: BookRecord) -> BookRecord:
        """
        Takes BookRecord.
        Returns NEW BookRecord.
        Must NOT mutate input.
        """
        raise NotImplementedError
