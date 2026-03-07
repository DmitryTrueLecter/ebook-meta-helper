from typing import List
from app.models.book import BookRecord
from app.metadata.reader.base import MetadataReader
from app.metadata.reader.fb2 import FB2MetadataReader
from app.metadata.reader.epub import EPUBMetadataReader

_READERS: List[MetadataReader] = [
    FB2MetadataReader(),
    EPUBMetadataReader(),
]

def read_metadata(record: BookRecord) -> BookRecord:
    for reader in _READERS:
        if reader.supports(record):
            return reader.read(record)
    return record
