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

                    self._set_text(metadata, "dc:title", record.title)
                    self._set_list(metadata, "dc:creator", record.authors)
                    self._set_text(metadata, "dc:language", record.language)

                    if record.year:
                        self._set_text(metadata, "dc:date", str(record.year))

                    if record.series:
                        meta = ET.SubElement(metadata, "meta")
                        meta.set("property", "belongs-to-collection")
                        meta.text = record.series
                        if record.series_index is not None:
                            idx = ET.SubElement(metadata, "meta")
                            idx.set("property", "group-position")
                            idx.text = str(record.series_index)

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

    def _find_opf(self, zin: zipfile.ZipFile) -> str | None:
        for name in zin.namelist():
            if name.lower().endswith(".opf"):
                return name
        return None

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
