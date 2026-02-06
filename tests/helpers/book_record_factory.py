from models.book import BookRecord


def make_record(
    *,
    title=None,
    authors=None,
    series=None,
    series_index=None,
    language=None,
    year=None,
    source=None,
    confidence=None,
):
    return BookRecord(
        path="dummy/path/book.epub",
        original_filename="book.epub",
        extension="epub",
        directories=["test"],
        title=title,
        authors=authors or [],
        series=series,
        series_index=series_index,
        language=language,
        year=year,
        source=source,
        confidence=confidence,
    )
