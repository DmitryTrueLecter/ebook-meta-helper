from datetime import date
from typing import Optional

from ebooklib import epub

from models.book import BookRecord
from metadata.reader.base import MetadataReader


class EPUBMetadataReader(MetadataReader):

    def supports(self, record: BookRecord) -> bool:
        return record.extension.lower() == "epub"

    def read(self, record: BookRecord) -> BookRecord:
        try:
            book = epub.read_epub(record.path)
        except Exception as e:
            record.errors.append(f"epub read error: {e}")
            return record

        # ---- Title ----
        if not record.title:
            titles = book.get_metadata("DC", "title")
            if titles:
                record.title = titles[0][0]

        # ---- Authors ----
        if not record.authors:
            creators = book.get_metadata("DC", "creator")
            record.authors = [c[0] for c in creators if c and c[0]]

        # ---- Language ----
        if not record.language:
            langs = book.get_metadata("DC", "language")
            if langs:
                record.language = langs[0][0]

        # ---- Publisher ----
        if not record.publisher:
            publishers = book.get_metadata("DC", "publisher")
            if publishers:
                record.publisher = publishers[0][0]

        # ---- Published date ----
        if not record.published:
            dates = book.get_metadata("DC", "date")
            if dates:
                parsed = self._parse_date(dates[0][0])
                if parsed:
                    record.published = parsed
                    if not record.year:
                        record.year = parsed.year

        # ---- Identifiers (ISBN) ----
        identifiers = book.get_metadata("DC", "identifier")
        for value, attrs in identifiers:
            if not value:
                continue
            v = value.replace("-", "")
            if not record.isbn13 and len(v) == 13 and v.isdigit():
                record.isbn13 = value
            elif not record.isbn10 and len(v) == 10 and v.isdigit():
                record.isbn10 = value

        # ---- Series (Calibre-compatible) ----
        if not record.series or record.series_index is None:
            metas = book.get_metadata("OPF", "meta")
            for value, attrs in metas:
                if not attrs:
                    continue
                name = attrs.get("name")
                content = attrs.get("content")

                if name == "calibre:series" and not record.series:
                    record.series = content
                elif name == "calibre:series_index" and record.series_index is None:
                    try:
                        record.series_index = int(float(content))
                    except Exception:
                        pass

        record.source = record.source or "file"
        return record

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        """
        EPUB dates are usually:
        - YYYY
        - YYYY-MM
        - YYYY-MM-DD
        """
        try:
            if len(value) == 4:
                return date(int(value), 1, 1)
            if len(value) == 7:
                y, m = value.split("-")
                return date(int(y), int(m), 1)
            if len(value) == 10:
                y, m, d = value.split("-")
                return date(int(y), int(m), int(d))
        except Exception:
            return None
        return None
