from app.ai.base import AIConfigSnapshot, EnrichOutcome
from app.ai.providers.dummy import DummyAIProvider
from app.models.book import BookRecord


def _config() -> AIConfigSnapshot:
    return AIConfigSnapshot(
        system_prompt="sys",
        cheap_model="cheap-model",
        expensive_model="expensive-model",
        escalation_threshold=0.7,
        response_format_ref="book_edition_info",
        provider="dummy",
        effort=None,
    )


def test_dummy_ai_provider_basic():
    provider = DummyAIProvider()
    record = BookRecord(
        path="x",
        original_filename="x",
        extension="fb2",
        directories=[]
    )

    outcome = provider.enrich(record, _config())

    assert isinstance(outcome, EnrichOutcome)
    assert outcome.record.title == "AI Title"
    assert outcome.record.source == "ai"
    assert len(outcome.calls) == 1
    assert outcome.calls[0].model == "cheap-model"
    assert outcome.calls[0].sequence == 0
    assert outcome.canonical_sequence == 0
