import zipfile
import tempfile
import shutil
import os
from xml.etree import ElementTree as ET

from metadata.writer.base import MetadataWriter, WriteResult
from models.book import BookRecord


OPF_NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


class EPUBMetadataWriter(MetadataWriter):
    extensions = {"epub"}

    def write(self, record: BookRecord) -> WriteResult:
        try:
            with zipfile.ZipFile(record.path, "r") as zin:
                opf_path = self._find_opf(zin)
                if not opf_path:
                    return WriteResult(False, errors=["epub: OPF not found"])

                with tempfile.TemporaryDirectory() as tmp:
                    zin.extractall(tmp)

                    opf_full = os.path.join(tmp, opf_path)
                    tree = ET.parse(opf_full)
                    root = tree.getroot()

                    metadata = root.find("opf:metadata", OPF_NS)
                    if metadata is None:
                        return WriteResult(False, errors=["epub: no metadata"])

                    # ---- Basic fields ----
                    epub_version = root.get("version", "2.0")
                    self._set_title(metadata, record.title, record.subtitle, epub_version)
                    self._set_list(metadata, "dc:creator", record.authors)
                    self._set_text(metadata, "dc:language", record.language)
                    self._set_text(metadata, "dc:publisher", record.publisher)

                    # ---- Description + OriginalWork ----
                    self._set_description(metadata, record)

                    # ---- Tags ----
                    self._set_list(metadata, "dc:subject", record.tags)

                    # ---- Dates ----
                    if record.published:
                        self._set_text(metadata, "dc:date", record.published)

                    # ---- Identifiers ----
                    self._set_identifier(metadata, "ISBN-10", record.isbn10)
                    self._set_identifier(metadata, "ISBN-13", record.isbn13)
                    self._set_meta(metadata, "asin", record.asin)

                    # ---- Series ----
                    if record.series:
                        self._set_meta(metadata, "belongs-to-collection", record.series)
                        if record.series_index is not None:
                            self._set_meta(metadata, "group-position", str(record.series_index))
                        if record.series_total is not None:
                            self._set_meta(metadata, "collection-total", str(record.series_total))

                    tree.write(opf_full, encoding="utf-8", xml_declaration=True)

                    tmp_epub = record.path + ".tmp"
                    with zipfile.ZipFile(tmp_epub, "w", zipfile.ZIP_DEFLATED) as zout:
                        for root_dir, _, files in os.walk(tmp):
                            for f in files:
                                full = os.path.join(root_dir, f)
                                rel = os.path.relpath(full, tmp)
                                zout.write(full, rel)

                    shutil.move(tmp_epub, record.path)

            return WriteResult(True)

        except Exception as e:
            return WriteResult(False, errors=[f"epub: {e}"])

    # ---------------- helpers ----------------

    def _find_opf(self, zin: zipfile.ZipFile) -> str | None:
        for name in zin.namelist():
            if name.lower().endswith(".opf"):
                return name
        return None

    def _set_title(
        self,
        meta: ET.Element,
        title: str | None,
        subtitle: str | None,
        epub_version: str,
    ) -> None:
        if not title and not subtitle:
            return

        dc_title_tag = f"{{{OPF_NS['dc']}}}title"

        # Remove all existing dc:title elements to avoid duplicates
        for el in meta.findall("dc:title", OPF_NS):
            meta.remove(el)
        # Remove any stale title-type refines
        for el in list(meta.findall("meta")):
            if (el.get("property") == "title-type"
                    and el.get("refines") in ("#subtitle", "#main-title")):
                meta.remove(el)

        if epub_version.startswith("3"):
            # EPUB 3: separate elements refined by title-type
            if title:
                el = ET.SubElement(meta, dc_title_tag)
                el.set("id", "main-title")
                el.text = title
            if subtitle:
                el = ET.SubElement(meta, dc_title_tag)
                el.set("id", "subtitle")
                el.text = subtitle
                refines = ET.SubElement(meta, "meta")
                refines.set("refines", "#subtitle")
                refines.set("property", "title-type")
                refines.text = "subtitle"
        else:
            # EPUB 2: merge into a single dc:title as "Title: Subtitle"
            combined = title or ""
            if subtitle:
                combined = f"{combined}: {subtitle}" if combined else subtitle
            el = ET.SubElement(meta, dc_title_tag)
            el.text = combined

    def _set_description(self, meta, record: BookRecord):
        parts = []

        if record.description:
            parts.append(record.description)

        orig = record.original
        if orig:
            orig_title_differs = orig.title and orig.title != record.title
            orig_authors_differ = orig.authors and orig.authors != record.authors

            if orig_title_differs or orig_authors_differ:
                block = []
                if orig.title:
                    block.append(f"Оригинальное название: {orig.title}")
                if orig.language:
                    block.append(f"Язык оригинала: {orig.language}")
                if orig.authors:
                    block.append(f"Автор: {', '.join(orig.authors)}")
                if block:
                    parts.append("\n".join(block))

        if not parts:
            return

        text = "\n\n".join(parts)
        el = meta.find("dc:description", OPF_NS)
        if el is None:
            el = ET.SubElement(meta, f"{{{OPF_NS['dc']}}}description")
        el.text = text

    def _set_text(self, meta, tag, value):
        if not value:
            return
        el = meta.find(tag, OPF_NS)
        if el is None:
            el = ET.SubElement(meta, f"{{{OPF_NS['dc']}}}{tag.split(':')[1]}")
        el.text = value

    def _set_list(self, meta, tag, values):
        if not values:
            return
        for el in meta.findall(tag, OPF_NS):
            meta.remove(el)
        for v in values:
            el = ET.SubElement(meta, f"{{{OPF_NS['dc']}}}{tag.split(':')[1]}")
            el.text = v

    def _set_identifier(self, meta, scheme, value):
        if not value:
            return
        el = ET.SubElement(meta, f"{{{OPF_NS['dc']}}}identifier")
        el.set("opf:scheme", scheme)
        el.text = value

    def _set_meta(self, meta, name, value):
        if not value:
            return
        el = ET.SubElement(meta, "meta")
        el.set("property", name)
        el.text = value