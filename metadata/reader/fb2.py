import xml.etree.ElementTree as ET

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
            if namespace:
                return f"{{{namespace}}}{tag}"
            return tag

        # Title
        title_el = root.find(f".//{q('book-title')}")
        if title_el is not None and title_el.text and not record.title:
            record.title = title_el.text.strip()

        # Authors
        authors = []
        for author in root.findall(f".//{q('author')}"):
            first = author.findtext(q("first-name"), default="").strip()
            last = author.findtext(q("last-name"), default="").strip()
            name = " ".join(p for p in (first, last) if p)
            if name:
                authors.append(name)

        if authors and not record.authors:
            record.authors = authors

        # Series
        sequence = root.find(f".//{q('sequence')}")
        if sequence is not None:
            if not record.series:
                record.series = sequence.attrib.get("name")
            if not record.series_index:
                num = sequence.attrib.get("number")
                if num and num.isdigit():
                    record.series_index = int(num)

        record.source = record.source or "file"
        return record
