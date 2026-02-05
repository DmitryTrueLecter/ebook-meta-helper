from typing import List
from models.book import BookRecord
from metadata.base import MetadataReader
from metadata.fb2_reader import FB2MetadataReader


_READERS: List[MetadataReader] = [
    FB2MetadataReader(),
    # EPUBMetadataReader(),  # later
]


def read_metadata(record: BookRecord) -> BookRecord:
    for reader in _READERS:
        if reader.supports(record):
            return reader.read(record)

    return record
