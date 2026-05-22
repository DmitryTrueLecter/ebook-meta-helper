import copy

import app.ai.providers  # noqa: F401 - triggers provider registration
from app.ai.registry import get
from app.models.book import BookRecord


def enrich(
    record: BookRecord,
    provider_name: str,
    hint: dict | None = None,
) -> BookRecord:
    provider = get(provider_name)
    record_copy = copy.deepcopy(record)
    return provider.enrich(record_copy, hint=hint)
