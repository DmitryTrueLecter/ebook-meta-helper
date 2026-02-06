from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from models.book import BookRecord


@dataclass
class WriteResult:
    success: bool
    skipped: bool = False
    errors: List[str] = field(default_factory=list)


class MetadataWriter(ABC):
    extensions: set[str]

    @abstractmethod
    def write(self, record: BookRecord) -> WriteResult:
        ...
