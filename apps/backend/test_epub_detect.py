#!/usr/bin/env python
"""Test EPUB detection."""

from pathlib import Path
import zipfile
import tempfile

from app.scanner.db_scanner import detect_format, _detect_epub_version

with tempfile.TemporaryDirectory() as tmp:
    # Test 1: EPUB 3.0
    epub_path = Path(tmp) / "test3.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""")
        zf.writestr("OEBPS/content.opf", """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0">
  <metadata></metadata>
</package>""")
    
    print(f"EPUB 3.0: {detect_format(epub_path)}")
    
    # Test 2: EPUB 2.0
    epub_path = Path(tmp) / "test2.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", """<?xml version="1.0"?>
<container><rootfiles><rootfile full-path="content.opf"/></rootfiles></container>""")
        zf.writestr("content.opf", """<?xml version="1.0"?>
<package version="2.0"><metadata></metadata></package>""")
    
    print(f"EPUB 2.0: {detect_format(epub_path)}")
    
    # Test 3: EPUB without version
    epub_path = Path(tmp) / "test_no_ver.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", """<container><rootfiles><rootfile full-path="x.opf"/></rootfiles></container>""")
        zf.writestr("x.opf", """<package><metadata></metadata></package>""")
    
    print(f"EPUB no version: {detect_format(epub_path)}")
    
    # Test 4: EPUB with no OPF found
    epub_path = Path(tmp) / "test_no_opf.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", """<container></container>""")
    
    print(f"EPUB no OPF: {detect_format(epub_path)}")
