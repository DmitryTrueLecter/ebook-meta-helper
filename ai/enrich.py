from models.book import BookRecord
import ai.providers  # triggers provider registration
from ai.registry import get


def enrich(record: BookRecord, provider_name: str) -> BookRecord:
    provider = get(provider_name)
    return provider.enrich(record)
