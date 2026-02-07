from typing import List

from metadata.reader.base import MetadataReader
from metadata.reader.fb2 import FB2MetadataReader
from models.book import BookRecord


_READERS: List[MetadataReader] = [
    FB2MetadataReader(),
    # EPUBMetadataReader(),  # later
]


def read_metadata(record: BookRecord) -> BookRecord:
    for reader in _READERS:
        if reader.supports(record):
            return reader.read(record)

    return record
