from app.ai.base import AIConfigSnapshot, EnrichOutcome
from app.models.book import BookRecord
from app.ai.enrich import enrich


def _config() -> AIConfigSnapshot:
    return AIConfigSnapshot(
        system_prompt="sys",
        cheap_model="cheap-model",
        expensive_model="expensive-model",
        escalation_threshold=0.7,
        response_format_ref="book_edition_info",
        provider="dummy",
        effort="high",
    )


def test_dummy_enrich_returns_outcome_with_calls():
    record = BookRecord(
        path="book.epub",
        original_filename="book.epub",
        extension="epub",
        directories=["sci-fi"],
        title="Old",
        authors=["Human"],
        source="file",
    )

    outcome = enrich(record, provider_name="dummy", config=_config())

    assert isinstance(outcome, EnrichOutcome)
    assert record.title == "Old"  # input not mutated
    assert outcome.record.title == "AI Title"
    assert outcome.record.authors == ["AI Author"]
    assert outcome.record.language == "en"
    assert outcome.record.source == "ai"
    assert outcome.record.confidence == 0.9


def test_dummy_enrich_outcome_has_valid_canonical_sequence():
    record = BookRecord(
        path="book.epub",
        original_filename="book.epub",
        extension="epub",
        directories=["sci-fi"],
    )

    outcome = enrich(record, provider_name="dummy", config=_config())

    assert len(outcome.calls) >= 1
    assert outcome.canonical_sequence == outcome.calls[outcome.canonical_sequence].sequence
    assert outcome.calls[0].tier in {"cheap", "expensive"}
