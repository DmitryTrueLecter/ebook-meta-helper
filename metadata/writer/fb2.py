from xml.etree import ElementTree as ET

from metadata.writer.base import MetadataWriter, WriteResult
from models.book import BookRecord


class FB2MetadataWriter(MetadataWriter):
    extensions = {"fb2"}

    def write(self, record: BookRecord) -> WriteResult:
        try:
            tree = ET.parse(record.path)
            root = tree.getroot()

            desc = root.find(".//description")
            if desc is None:
                return WriteResult(False, errors=["fb2: no description"])

            title_info = desc.find("title-info")
            if title_info is None:
                title_info = ET.SubElement(desc, "title-info")

            if record.title:
                el = title_info.find("book-title")
                if el is None:
                    el = ET.SubElement(title_info, "book-title")
                el.text = record.title

            if record.authors:
                for a in title_info.findall("author"):
                    title_info.remove(a)
                for name in record.authors:
                    parts = name.split(" ", 1)
                    author = ET.SubElement(title_info, "author")
                    ET.SubElement(author, "first-name").text = parts[0]
                    if len(parts) > 1:
                        ET.SubElement(author, "last-name").text = parts[1]

            if record.series:
                seq = title_info.find("sequence")
                if seq is None:
                    seq = ET.SubElement(title_info, "sequence")
                seq.set("name", record.series)
                if record.series_index is not None:
                    seq.set("number", str(record.series_index))

            if record.language:
                lang = title_info.find("lang")
                if lang is None:
                    lang = ET.SubElement(title_info, "lang")
                lang.text = record.language

            if record.year:
                pub = desc.find("publish-info")
                if pub is None:
                    pub = ET.SubElement(desc, "publish-info")
                year = pub.find("year")
                if year is None:
                    year = ET.SubElement(pub, "year")
                year.text = str(record.year)

            tree.write(record.path, encoding="utf-8", xml_declaration=True)
            return WriteResult(True)

        except Exception as e:
            return WriteResult(False, errors=[f"fb2: {e}"])
