from typing import List

from app.metadata.reader.base import MetadataReader
from app.metadata.reader.fb2 import FB2MetadataReader
from app.models.book import BookRecord


_READERS: List[MetadataReader] = [
    FB2MetadataReader(),
    # EPUBMetadataReader(),  # later
]


def read_metadata(record: BookRecord) -> BookRecord:
    for reader in _READERS:
        if reader.supports(record):
            return reader.read(record)

    return record
