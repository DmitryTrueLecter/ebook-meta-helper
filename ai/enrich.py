from models.book import BookRecord
import ai.providers  # triggers provider registration
from ai.registry import get
import copy

def enrich(record: BookRecord, provider_name: str) -> BookRecord:
    provider = get(provider_name)
    record_copy = copy.deepcopy(record)
    return provider.enrich(record_copy)
