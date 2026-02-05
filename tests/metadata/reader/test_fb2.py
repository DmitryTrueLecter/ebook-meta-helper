from metadata import read_metadata
from models.book import BookRecord


def test_fb2_basic_metadata(tmp_path):
    fb2 = tmp_path / "book.fb2"
    fb2.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
        <FictionBook>
          <description>
            <title-info>
              <book-title>Test Book</book-title>
              <author>
                <first-name>John</first-name>
                <last-name>Doe</last-name>
              </author>
            </title-info>
          </description>
        </FictionBook>
        """,
        encoding="utf-8"
    )

    record = BookRecord(
        path=str(fb2),
        original_filename="book.fb2",
        extension="fb2",
        directories=[]
    )

    record = read_metadata(record)

    assert record.title == "Test Book"
    assert record.authors == ["John Doe"]

def test_fb2_with_namespace(tmp_path):
    fb2 = tmp_path / "book.fb2"
    fb2.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
        <FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
          <description>
            <title-info>
              <book-title>Namespaced Book</book-title>
              <author>
                <first-name>Jane</first-name>
                <last-name>Smith</last-name>
              </author>
            </title-info>
          </description>
        </FictionBook>
        """,
        encoding="utf-8"
    )

    record = BookRecord(
        path=str(fb2),
        original_filename="book.fb2",
        extension="fb2",
        directories=[]
    )

    record = read_metadata(record)

    assert record.title == "Namespaced Book"
    assert record.authors == ["Jane Smith"]

def test_fb2_without_author(tmp_path):
    fb2 = tmp_path / "book.fb2"
    fb2.write_text(
        """<FictionBook>
          <description>
            <title-info>
              <book-title>Authorless Book</book-title>
            </title-info>
          </description>
        </FictionBook>""",
        encoding="utf-8"
    )

    record = BookRecord(
        path=str(fb2),
        original_filename="book.fb2",
        extension="fb2",
        directories=[]
    )

    record = read_metadata(record)

    assert record.title == "Authorless Book"
    assert record.authors == []

def test_fb2_without_title(tmp_path):
    fb2 = tmp_path / "book.fb2"
    fb2.write_text(
        """<FictionBook>
          <description>
            <title-info>
              <author>
                <first-name>John</first-name>
                <last-name>Doe</last-name>
              </author>
            </title-info>
          </description>
        </FictionBook>""",
        encoding="utf-8"
    )

    record = BookRecord(
        path=str(fb2),
        original_filename="book.fb2",
        extension="fb2",
        directories=[]
    )

    record = read_metadata(record)

    assert record.title is None
    assert record.authors == ["John Doe"]

def test_fb2_multiple_authors(tmp_path):
    fb2 = tmp_path / "book.fb2"
    fb2.write_text(
        """<FictionBook>
          <description>
            <title-info>
              <book-title>Multi Author</book-title>
              <author>
                <first-name>John</first-name>
                <last-name>Doe</last-name>
              </author>
              <author>
                <first-name>Jane</first-name>
                <last-name>Smith</last-name>
              </author>
            </title-info>
          </description>
        </FictionBook>""",
        encoding="utf-8"
    )

    record = BookRecord(
        path=str(fb2),
        original_filename="book.fb2",
        extension="fb2",
        directories=[]
    )

    record = read_metadata(record)

    assert record.authors == ["John Doe", "Jane Smith"]

def test_fb2_series(tmp_path):
    fb2 = tmp_path / "book.fb2"
    fb2.write_text(
        """<FictionBook>
          <description>
            <title-info>
              <book-title>Series Book</book-title>
              <sequence name="Horus Heresy" number="3"/>
            </title-info>
          </description>
        </FictionBook>""",
        encoding="utf-8"
    )

    record = BookRecord(
        path=str(fb2),
        original_filename="book.fb2",
        extension="fb2",
        directories=[]
    )

    record = read_metadata(record)

    assert record.series == "Horus Heresy"
    assert record.series_index == 3

def test_fb2_invalid_xml(tmp_path):
    fb2 = tmp_path / "book.fb2"
    fb2.write_text("<FictionBook><broken>", encoding="utf-8")

    record = BookRecord(
        path=str(fb2),
        original_filename="book.fb2",
        extension="fb2",
        directories=[]
    )

    record = read_metadata(record)

    assert record.errors
    assert record.title is None


def test_fb2_does_not_override_existing_fields(tmp_path):
    fb2 = tmp_path / "book.fb2"
    fb2.write_text(
        """<FictionBook>
          <description>
            <title-info>
              <book-title>Original Title</book-title>
            </title-info>
          </description>
        </FictionBook>""",
        encoding="utf-8"
    )

    record = BookRecord(
        path=str(fb2),
        original_filename="book.fb2",
        extension="fb2",
        directories=[],
        title="Predefined Title"
    )

    record = read_metadata(record)

    assert record.title == "Predefined Title"
