from app.models.book import BookRecord
import app.ai.providers  # triggers provider registration
from app.ai.registry import get
import copy

def enrich(record: BookRecord, provider_name: str) -> BookRecord:
    provider = get(provider_name)
    record_copy = copy.deepcopy(record)
    return provider.enrich(record_copy)
