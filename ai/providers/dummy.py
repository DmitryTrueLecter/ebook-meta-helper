from copy import deepcopy
from models.book import BookRecord
from ai.base import AIProvider


class DummyAIProvider(AIProvider):
    name = "dummy"

    def enrich(self, record: BookRecord) -> BookRecord:
        new = deepcopy(record)

        new.title = "AI Title"
        new.authors = ["AI Author"]
        new.language = "en"

        new.source = "ai"
        new.confidence = 0.9

        return new
