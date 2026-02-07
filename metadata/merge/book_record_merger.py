from typing import List, Optional
from copy import deepcopy

from models.book import BookRecord, OriginalWork


SOURCE_PRIORITY = {
    "ai": 3,
    "file": 2,
    None: 1,
}


def merge_book_records(records: List[BookRecord]) -> BookRecord:
    if not records:
        raise ValueError("no records to merge")

    records = sorted(
        records,
        key=lambda r: SOURCE_PRIORITY.get(r.source, 0),
        reverse=True,
    )

    base = deepcopy(records[0])

    for record in records[1:]:
        _merge_into(base, record)

    if len({r.source for r in records if r.source}) > 1:
        base.source = "mixed"

    base.confidence = max(
        (r.confidence for r in records if r.confidence is not None),
        default=base.confidence,
    )

    return base


def _merge_into(target: BookRecord, incoming: BookRecord) -> None:
    for field in (
        "title",
        "series",
        "series_index",
        "language",
        "year",
    ):
        if getattr(target, field) is None and getattr(incoming, field) is not None:
            setattr(target, field, getattr(incoming, field))

    if not target.authors and incoming.authors:
        target.authors = list(incoming.authors)

    if target.original is None and incoming.original is not None:
        target.original = _merge_original(incoming.original)

    target.errors.extend(incoming.errors)
    target.notes.extend(incoming.notes)


def _merge_original(original: OriginalWork) -> OriginalWork:
    return OriginalWork(
        title=original.title,
        authors=list(original.authors),
        language=original.language,
        year=original.year,
    )
