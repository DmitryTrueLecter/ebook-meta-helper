from ai.prompt.book_metadata_v1 import build_book_metadata_prompt
from models.book import BookRecord, OriginalWork


def test_prompt_contains_required_sections():
    record = BookRecord(
        path="x",
        original_filename="Horus_Rising.fb2",
        extension="fb2",
        directories=["warhammer", "heresy"],
        title="Восхождение Хоруса",
        authors=["Дэн Абнетт"],
        language="ru",
        original=OriginalWork(
            title="Horus Rising",
            authors=["Dan Abnett"],
            language="en",
        ),
    )

    prompt = build_book_metadata_prompt(record)

    assert "ONLY with valid JSON" in prompt
    assert '"edition"' in prompt
    assert '"original"' in prompt
    assert "Horus_Rising.fb2" in prompt
    assert "warhammer / heresy" in prompt
    assert "Восхождение Хоруса" in prompt
    assert "Horus Rising" in prompt
