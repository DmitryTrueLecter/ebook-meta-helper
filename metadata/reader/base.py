from abc import ABC, abstractmethod
from models.book import BookRecord


class MetadataReader(ABC):

    @abstractmethod
    def supports(self, record: BookRecord) -> bool:
        pass

    @abstractmethod
    def read(self, record: BookRecord) -> BookRecord:
        pass
