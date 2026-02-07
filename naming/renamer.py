import re
from typing import Optional

from models.book import BookRecord
from naming.formatter import format_value
from naming.placeholders import PLACEHOLDERS

_PATTERN = re.compile(r"\{([^}:]+)(?::([^}]+))?\}")


class RenameError(Exception):
    pass


def build_filename(
    record: BookRecord,
    template: str,
    *,
    missing: str = "skip",  # skip | empty | error
) -> str:
    def replace(match: re.Match) -> str:
        name = match.group(1)
        fmt = match.group(2)

        resolver = PLACEHOLDERS.get(name)
        if not resolver:
            raise RenameError(f"unknown placeholder: {name}")

        raw = resolver(record)
        value = format_value(raw, fmt)

        if value is None:
            if missing == "skip":
                return ""
            if missing == "empty":
                return ""
            if missing == "error":
                raise RenameError(f"missing value for {name}")

        return value

    result = _PATTERN.sub(replace, template)
    return _cleanup(result)


def _cleanup(name: str) -> str:
    # убрать лишние пробелы и разделители
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[ _.-]+$", "", name)
    return name.strip()
