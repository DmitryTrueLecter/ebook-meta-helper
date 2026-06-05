from datetime import date
from typing import Any, Callable, Dict, Optional

from app.models.book import BookRecord


def _join_authors(record: BookRecord) -> Optional[str]:
    if not record.authors:
        return None
    return ", ".join(record.authors)


def _published_date(record: BookRecord) -> Optional[date]:
    # Пока в модели только year
    if record.year:
        return date(record.year, 1, 1)
    return None


PLACEHOLDERS: Dict[str, Callable[[BookRecord], Any]] = {
    # Text
    "Title": lambda r: r.title,
    "SeriesName": lambda r: r.series,
    "Authors": _join_authors,
    "Language": lambda r: r.language,
    "Subtitle": lambda r: r.subtitle,
    "Publisher": lambda r: r.publisher,

    # Numbers
    "SeriesNumber": lambda r: r.series_index,
    "SeriesTotal": lambda r: r.series_total,

    # Identifiers
    "ISBN10": lambda r: r.isbn10,
    "ISBN13": lambda r: r.isbn13,
    "ASIN": lambda r: r.asin,

    # Dates
    "Published": _published_date,
}
