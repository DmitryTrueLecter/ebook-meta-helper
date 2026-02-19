import xml.etree.ElementTree as ET
from datetime import date

from models.book import BookRecord
from metadata.reader.base import MetadataReader


class FB2MetadataReader(MetadataReader):

    def supports(self, record: BookRecord) -> bool:
        return record.extension.lower() == "fb2"

    def read(self, record: BookRecord) -> BookRecord:
        try:
            tree = ET.parse(record.path)
            root = tree.getroot()
        except Exception as e:
            record.errors.append(f"fb2 parse error: {e}")
            return record

        namespace = None
        if root.tag.startswith("{"):
            namespace = root.tag.split("}")[0].strip("{")

        def q(tag: str) -> str:
            return f"{{{namespace}}}{tag}" if namespace else tag

        # ---- Title ----
        title_el = root.find(f".//{q('book-title')}")
        if title_el is not None and title_el.text and not record.title:
            record.title = title_el.text.strip()

        # ---- Subtitle ----
        subtitle_el = root.find(f".//{q('subtitle')}")
        if subtitle_el is not None and subtitle_el.text and not record.subtitle:
            record.subtitle = subtitle_el.text.strip()

        # ---- Authors ----
        if not record.authors:
            authors = []
            for author in root.findall(f".//{q('author')}"):
                first = author.findtext(q("first-name"), default="").strip()
                last = author.findtext(q("last-name"), default="").strip()
                middle = author.findtext(q("middle-name"), default="").strip()
                name = " ".join(p for p in (first, middle, last) if p)
                if name:
                    authors.append(name)
            if authors:
                record.authors = authors

        # ---- Description ----
        if not record.description:
            annotation_el = root.find(f".//{q('annotation')}")
            if annotation_el is not None:
                # annotation may contain child tags (p, strong, etc.) — collect all text
                text = "".join(annotation_el.itertext()).strip()
                if text:
                    record.description = text

        # ---- Tags (keywords) ----
        if not record.tags:
            keywords_el = root.find(f".//{q('keywords')}")
            if keywords_el is not None and keywords_el.text:
                tags = [t.strip() for t in keywords_el.text.split(",") if t.strip()]
                if tags:
                    record.tags = tags

        # ---- Language ----
        lang_el = root.find(f".//{q('lang')}")
        if lang_el is not None and lang_el.text and not record.language:
            record.language = lang_el.text.strip()

        # ---- Series ----
        sequence = root.find(f".//{q('sequence')}")
        if sequence is not None:
            if not record.series:
                record.series = sequence.attrib.get("name")
            if record.series_index is None:
                num = sequence.attrib.get("number")
                if num and num.isdigit():
                    record.series_index = int(num)

        # ---- Publisher ----
        publisher_el = root.find(f".//{q('publish-info')}/{q('publisher')}")
        if publisher_el is not None and publisher_el.text and not record.publisher:
            record.publisher = publisher_el.text.strip()

        # ---- Published / Year ----
        year_el = root.find(f".//{q('publish-info')}/{q('year')}")
        if year_el is not None and year_el.text:
            try:
                y = int(year_el.text.strip())
                if not record.year:
                    record.year = y
                if not record.published:
                    record.published = date(y, 1, 1)
            except ValueError:
                pass

        # ---- ISBN ----
        isbn_el = root.find(f".//{q('publish-info')}/{q('isbn')}")
        if isbn_el is not None and isbn_el.text:
            isbn = isbn_el.text.replace("-", "").strip()
            if len(isbn) == 13 and isbn.isdigit() and not record.isbn13:
                record.isbn13 = isbn_el.text.strip()
            elif len(isbn) == 10 and isbn.isdigit() and not record.isbn10:
                record.isbn10 = isbn_el.text.strip()

        record.source = record.source or "file"
        return record