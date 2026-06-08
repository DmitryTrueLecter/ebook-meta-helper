import copy
from typing import Optional

import app.ai.providers  # noqa: F401 - triggers provider registration
from app.ai.base import AIConfigSnapshot, EnrichOutcome
from app.ai.registry import get
from app.models.book import BookRecord


def enrich(
    record: BookRecord,
    provider_name: str,
    config: AIConfigSnapshot,
    directory_hint: Optional[dict] = None,
) -> EnrichOutcome:
    provider = get(provider_name)
    record_copy = copy.deepcopy(record)
    return provider.enrich(record_copy, config, directory_hint=directory_hint)
