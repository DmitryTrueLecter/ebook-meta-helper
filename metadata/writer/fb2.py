from lxml import etree

from metadata.writer.base import MetadataWriter, WriteResult
from models.book import BookRecord


class FB2MetadataWriter(MetadataWriter):
    extensions = {"fb2"}

    def write(self, record: BookRecord) -> WriteResult:
        try:
            parser = etree.XMLParser(remove_blank_text=False)
            tree = etree.parse(record.path, parser)
            root = tree.getroot()

            # Extract the primary namespace URI from the root tag
            nsmap = root.nsmap
            fb2_ns = None
            for prefix, uri in nsmap.items():
                if "fictionbook" in uri.lower():
                    fb2_ns = uri
                    break
            # Fall back to the default namespace (prefix=None) or the first available one
            if fb2_ns is None:
                fb2_ns = nsmap.get(None) or next(iter(nsmap.values()), "")

            def q(tag: str) -> str:
                return f"{{{fb2_ns}}}{tag}" if fb2_ns else tag

            def find(el, tag):
                return el.find(q(tag))

            def sub(parent, tag):
                return etree.SubElement(parent, q(tag))

            desc = root.find(f".//{q('description')}")
            if desc is None:
                return WriteResult(False, errors=["fb2: no description"])

            title_info = find(desc, "title-info")
            if title_info is None:
                title_info = sub(desc, "title-info")

            # ---- Title ----

            if record.title:
                el = find(title_info, "book-title")
                if el is None:
                    el = sub(title_info, "book-title")
                el.text = record.title

            # ---- Subtitle ----
            if record.subtitle:
                el = find(title_info, "subtitle")
                if el is None:
                    el = sub(title_info, "subtitle")
                el.text = record.subtitle

            # ---- Authors ----
            if record.authors:
                for a in title_info.findall(q("author")):
                    title_info.remove(a)

                for name in record.authors:
                    author = sub(title_info, "author")
                    parts = name.split(" ", 1)
                    sub(author, "first-name").text = parts[0]
                    if len(parts) > 1:
                        sub(author, "last-name").text = parts[1]

            # ---- Annotation (description + OriginalWork) ----
            has_description = bool(record.description)
            has_original = (
                record.original is not None
                and (
                    (record.original.title and record.original.title != record.title)
                    or (record.original.authors and record.original.authors != record.authors)
                )
            )

            if has_description or has_original or record.tags:
                annotation = find(title_info, "annotation")
                if annotation is None:
                    annotation = sub(title_info, "annotation")
                else:
                    for child in list(annotation):
                        annotation.remove(child)
                    annotation.text = None

                if has_description:
                    p = sub(annotation, "p")
                    p.text = record.description

                if has_original:
                    orig = record.original
                    if orig.title and orig.title != record.title:
                        p = sub(annotation, "p")
                        p.text = f"Оригинальное название: {orig.title}"

                    if orig.language:
                        p = sub(annotation, "p")
                        p.text = f"Язык оригинала: {orig.language}"

                    if orig.authors and orig.authors != record.authors:
                        p = sub(annotation, "p")
                        p.text = f"Автор: {', '.join(orig.authors)}"

                # Append tags to annotation so readers that don't parse <keywords> still show them
                if record.tags:
                    p = sub(annotation, "p")
                    p.text = f"Теги: {', '.join(record.tags)}"

            # ---- Keywords (tags) ----
            # Per FB2 spec, <keywords> must come after <annotation>.
            # We write it fresh and then move it to the correct position.
            if record.tags:
                # Remove existing keywords element if present
                existing_kw = find(title_info, "keywords")
                if existing_kw is not None:
                    title_info.remove(existing_kw)

                # Create new keywords element
                kw_el = etree.SubElement(title_info, q("keywords"))
                kw_el.text = ", ".join(record.tags)

                # Move it to just after <annotation> (or <book-title> if no annotation)
                annotation_el = find(title_info, "annotation")
                anchor = annotation_el if annotation_el is not None else find(title_info, "book-title")
                if anchor is not None:
                    anchor_idx = list(title_info).index(anchor)
                    title_info.remove(kw_el)
                    title_info.insert(anchor_idx + 1, kw_el)

            # ---- Series ----
            if record.series:
                seq = find(title_info, "sequence")
                if seq is None:
                    seq = sub(title_info, "sequence")
                seq.set("name", record.series)
                if record.series_index is not None:
                    seq.set("number", str(record.series_index))

            # ---- Language ----
            if record.language:
                el = find(title_info, "lang")
                if el is None:
                    el = sub(title_info, "lang")
                el.text = record.language

            # ---- Publish info ----
            pub = find(desc, "publish-info")
            if pub is None:
                pub = sub(desc, "publish-info")

            if record.publisher:
                el = find(pub, "publisher")
                if el is None:
                    el = sub(pub, "publisher")
                el.text = record.publisher

            if record.published:
                el = find(pub, "year")
                if el is None:
                    el = sub(pub, "year")
                el.text = str(record.published)[:4]

            if record.isbn13 or record.isbn10:
                el = find(pub, "isbn")
                if el is None:
                    el = sub(pub, "isbn")
                el.text = record.isbn13 or record.isbn10

            # ---- Custom info (non-standard) ----
            self._set_custom(desc, q, "asin", record.asin)
            self._set_custom(desc, q, "series_total", record.series_total)

            tree.write(
                record.path,
                encoding="utf-8",
                xml_declaration=True,
                pretty_print=False,
            )
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
        el = etree.SubElement(desc, q("custom-info"))
        el.set("info-type", name)
        el.text = str(value)