from ai.base import AIProvider
from models.book import BookRecord, OriginalWork


class DummyAIProvider(AIProvider):
    name = "dummy"

    def enrich(self, record: BookRecord) -> BookRecord:
        # Edition (this file)
        record.title = "Dummy Edition Title"
        record.authors = ["Dummy Author"]
        record.series = "Dummy Series"
        record.series_index = 1
        record.language = "ru"
        record.year = 2000

        # Original work
        record.original = OriginalWork(
            title="Dummy Original Title",
            authors=["Dummy Original Author"],
            language="en",
            year=1999,
        )

        record.source = "ai"
        record.confidence = 1.0

        return record
