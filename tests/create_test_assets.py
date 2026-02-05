# create_test_assets.py

import json
from pathlib import Path
from ebooklib import epub

# --- EPUB ---
def create_epub(assets_dir, filename, title, authors, language="en"):
    book = epub.EpubBook()
    book.set_identifier(filename)
    book.set_title(title)
    book.set_language(language)
    for a in authors:
        book.add_author(a)

    chapter = epub.EpubHtml(title='Intro', file_name='chap_1.xhtml', lang=language)
    chapter.content = '<h1>Hello EPUB</h1>'
    book.add_item(chapter)

    book.toc = (chapter,)
    book.spine = ['nav', chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub_path = assets_dir / f"{filename}.epub"
    epub.write_epub(epub_path, book)

    # JSON
    json_path = epub_path.with_suffix(".json")
    json_path.write_text(json.dumps({"title": title, "authors": authors, "language": language}, indent=2), encoding="utf-8")


# --- FB2 ---
def create_fb2(assets_dir, filename, title, authors, series=None, series_index=None, namespace=False):
    ns_attr = ' xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"' if namespace else ""

    authors_xml_list = []
    for a in authors:
        parts = a.split()
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""
        authors_xml_list.append(f"<author><first-name>{first_name}</first-name><last-name>{last_name}</last-name></author>")

    authors_xml = "".join(authors_xml_list)
    series_xml = f'<sequence name="{series}" number="{series_index}"/>' if series else ""

    fb2_content = f"""<?xml version="1.0" encoding="utf-8"?>
<FictionBook{ns_attr}>
  <description>
    <title-info>
      <book-title>{title}</book-title>
      {authors_xml}
      {series_xml}
    </title-info>
  </description>
</FictionBook>
"""

    fb2_path = assets_dir / f"{filename}.fb2"
    fb2_path.write_text(fb2_content, encoding="utf-8")

    # JSON
    data = {"title": title, "authors": authors}
    if series:
        data["series"] = series
    if series_index:
        data["series_index"] = series_index

    json_path = fb2_path.with_suffix(".json")
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main():
    epub_dir = Path("assets/epub")
    fb2_dir = Path("assets/fb2")
    epub_dir.mkdir(parents=True, exist_ok=True)
    fb2_dir.mkdir(parents=True, exist_ok=True)

    # EPUB
    create_epub(epub_dir, "single_author", "Live EPUB Test", ["Alice"])
    create_epub(epub_dir, "multiple_authors", "Multi EPUB", ["Alice", "Bob"])

    # FB2
    create_fb2(fb2_dir, "no_namespace", "No Namespace Book", ["John Doe"])
    create_fb2(fb2_dir, "with_namespace", "Namespaced Book", ["Jane Smith"], namespace=True)
    create_fb2(fb2_dir, "series", "Series Book", ["Author"], series="Horus Heresy", series_index=3)


if __name__ == "__main__":
    main()
    print("Test assets generated in assets/")
