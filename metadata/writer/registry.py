from typing import Dict

from metadata.writer.base import MetadataWriter, WriteResult
from models.book import BookRecord

_WRITERS: Dict[str, MetadataWriter] = {}


def register(writer: MetadataWriter) -> None:
    for ext in writer.extensions:
        _WRITERS[ext.lower()] = writer


def write_metadata(record: BookRecord) -> WriteResult:
    writer = _WRITERS.get(record.extension.lower())
    if not writer:
        return WriteResult(success=False, skipped=True)
    return writer.write(record)
