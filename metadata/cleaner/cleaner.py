from copy import deepcopy
from typing import Optional

from models.book import BookRecord, OriginalWork
from metadata.cleaner.null_equivalents import NULL_EQUIVALENT_STRINGS


def _is_null_equivalent(value: str) -> bool:
    return value.strip().lower() in NULL_EQUIVALENT_STRINGS


def _clean_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return None if _is_null_equivalent(value) else value


def _clean_str_list(values: list[str]) -> list[str]:
    return [v for v in values if not _is_null_equivalent(v)]


def _clean_original(original: Optional[OriginalWork]) -> Optional[OriginalWork]:
    if original is None:
        return None

    original.title = _clean_str(original.title)
    original.language = _clean_str(original.language)
    original.authors = _clean_str_list(original.authors)

    # Если после очистки в original ничего не осталось — убираем весь объект
    has_data = any([
        original.title,
        original.language,
        original.authors,
        original.year is not None,
    ])
    return original if has_data else None


def clean_record(record: BookRecord) -> BookRecord:
    """
    Возвращает копию записи, в которой псевдопустые значения
    (см. null_equivalents.py) заменены на None / пустой список.
    Исходная запись не изменяется.
    """
    record = deepcopy(record)

    record.title = _clean_str(record.title)
    record.subtitle = _clean_str(record.subtitle)
    record.series = _clean_str(record.series)
    record.language = _clean_str(record.language)
    record.publisher = _clean_str(record.publisher)
    record.description = _clean_str(record.description)

    record.authors = _clean_str_list(record.authors)
    record.tags = _clean_str_list(record.tags)

    record.original = _clean_original(record.original)

    return record