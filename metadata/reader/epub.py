from models.book import BookRecord
from metadata.reader.base import MetadataReader
from ebooklib import epub


class EPUBMetadataReader(MetadataReader):

    def supports(self, record: BookRecord) -> bool:
        return record.extension.lower() == "epub"

    def read(self, record: BookRecord) -> BookRecord:
        try:
            book = epub.read_epub(record.path)
        except Exception as e:
            record.errors.append(f"epub read error: {e}")
            return record

        # Title
        if not record.title:
            titles = book.get_metadata("DC", "title")
            if titles:
                record.title = titles[0][0]

        # Authors
        if not record.authors:
            creators = book.get_metadata("DC", "creator")
            record.authors = [c[0] for c in creators if c[0]]

        # Language
        if not record.language:
            langs = book.get_metadata("DC", "language")
            if langs:
                record.language = langs[0][0]

        record.source = record.source or "file"
        return record
