from ai.providers.dummy import DummyAIProvider
from models.book import BookRecord


def test_dummy_ai_provider_basic():
    provider = DummyAIProvider()
    record = BookRecord(
        path="x",
        original_filename="x",
        extension="fb2",
        directories=[]
    )

    result = provider.enrich(record)

    assert result.title == "AI Title"
    assert result.source == "ai"