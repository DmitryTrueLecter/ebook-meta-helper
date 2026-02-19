from xml.etree import ElementTree as ET

from metadata.writer.base import MetadataWriter, WriteResult
from models.book import BookRecord


class FB2MetadataWriter(MetadataWriter):
    extensions = {"fb2"}

    def write(self, record: BookRecord) -> WriteResult:
        try:
            tree = ET.parse(record.path)
            root = tree.getroot()

            ns = ""
            if root.tag.startswith("{"):
                ns = root.tag.split("}")[0] + "}"

            def q(tag: str) -> str:
                return f"{ns}{tag}"

            desc = root.find(f".//{q('description')}")
            if desc is None:
                return WriteResult(False, errors=["fb2: no description"])

            title_info = desc.find(q("title-info"))
            if title_info is None:
                title_info = ET.SubElement(desc, q("title-info"))

            # ---- Title ----
            if record.title:
                el = title_info.find(q("book-title"))
                if el is None:
                    el = ET.SubElement(title_info, q("book-title"))
                el.text = record.title

            # ---- Subtitle ----
            if record.subtitle:
                el = title_info.find(q("subtitle"))
                if el is None:
                    el = ET.SubElement(title_info, q("subtitle"))
                el.text = record.subtitle

            # ---- Authors ----
            if record.authors:
                for a in title_info.findall(q("author")):
                    title_info.remove(a)

                for name in record.authors:
                    author = ET.SubElement(title_info, q("author"))
                    parts = name.split(" ", 1)
                    ET.SubElement(author, q("first-name")).text = parts[0]
                    if len(parts) > 1:
                        ET.SubElement(author, q("last-name")).text = parts[1]

            # ---- Annotation (description + OriginalWork) ----
            has_description = bool(record.description)
            has_original = (
                record.original is not None
                and (
                    (record.original.title and record.original.title != record.title)
                    or (record.original.authors and record.original.authors != record.authors)
                )
            )

            if has_description or has_original:
                annotation = title_info.find(q("annotation"))
                if annotation is None:
                    annotation = ET.SubElement(title_info, q("annotation"))
                else:
                    # Clear existing content
                    for child in list(annotation):
                        annotation.remove(child)
                    annotation.text = None

                if has_description:
                    p = ET.SubElement(annotation, q("p"))
                    p.text = record.description

                if has_original:
                    orig = record.original
                    if orig.title and orig.title != record.title:
                        p = ET.SubElement(annotation, q("p"))
                        p.text = f"Оригинальное название: {orig.title}"

                    if orig.language:
                        p = ET.SubElement(annotation, q("p"))
                        p.text = f"Язык оригинала: {orig.language}"

                    if orig.authors and orig.authors != record.authors:
                        p = ET.SubElement(annotation, q("p"))
                        p.text = f"Автор: {', '.join(orig.authors)}"

            # ---- Keywords (tags) ----
            if record.tags:
                el = title_info.find(q("keywords"))
                if el is None:
                    el = ET.SubElement(title_info, q("keywords"))
                el.text = ", ".join(record.tags)

            # ---- Series ----
            if record.series:
                seq = title_info.find(q("sequence"))
                if seq is None:
                    seq = ET.SubElement(title_info, q("sequence"))
                seq.set("name", record.series)
                if record.series_index is not None:
                    seq.set("number", str(record.series_index))

            # ---- Language ----
            if record.language:
                el = title_info.find(q("lang"))
                if el is None:
                    el = ET.SubElement(title_info, q("lang"))
                el.text = record.language

            # ---- Publish info ----
            pub = desc.find(q("publish-info"))
            if pub is None:
                pub = ET.SubElement(desc, q("publish-info"))

            if record.publisher:
                el = pub.find(q("publisher"))
                if el is None:
                    el = ET.SubElement(pub, q("publisher"))
                el.text = record.publisher

            if record.published:
                el = pub.find(q("year"))
                if el is None:
                    el = ET.SubElement(pub, q("year"))
                el.text = str(record.published)[:4]

            if record.isbn13 or record.isbn10:
                el = pub.find(q("isbn"))
                if el is None:
                    el = ET.SubElement(pub, q("isbn"))
                el.text = record.isbn13 or record.isbn10

            # ---- Custom info (non-standard) ----
            self._set_custom(desc, q, "asin", record.asin)
            self._set_custom(desc, q, "series_total", record.series_total)

            tree.write(record.path, encoding="utf-8", xml_declaration=True)
            return WriteResult(True)

        except Exception as e:
            return WriteResult(False, errors=[f"fb2: {e}"])

    def _set_custom(self, desc, q, name, value):
        if not value:
            return
        for el in desc.findall(q("custom-info")):
            if el.get("info-type") == name:
                el.text = str(value)
                return
        el = ET.SubElement(desc, q("custom-info"))
        el.set("info-type", name)
        el.text = str(value)