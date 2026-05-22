import copy
from typing import Optional

import app.ai.providers  # triggers provider registration  # noqa: F401
from app.ai.registry import get
from app.models.book import BookRecord


def enrich(
    record: BookRecord,
    provider_name: str,
    directory_hint: Optional[dict] = None,
) -> BookRecord:
    provider = get(provider_name)
    record_copy = copy.deepcopy(record)
    return provider.enrich(record_copy, directory_hint=directory_hint)
