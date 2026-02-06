from ai.base import AIProvider
from models.book import BookRecord, OriginalWork

class DummyAIProvider(AIProvider):
    name = "dummy"

    def enrich(self, record: BookRecord) -> BookRecord:
        record.title = "AI Title"
        record.authors = ["AI Author"]
        record.language = "en"

        record.source = "ai"
        record.confidence = 0.9

        return record
