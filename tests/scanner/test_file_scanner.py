from scanner.file_scanner import scan_file
import pytest


def test_scan_simple_file(tmp_path):
    root = tmp_path / "new_books"
    book_dir = root / "warhammer 40k" / "dark angels"
    book_dir.mkdir(parents=True)

    file_path = book_dir / "book.fb2"
    file_path.write_text("dummy")

    record = scan_file(str(file_path), str(root))

    assert record.original_filename == "book.fb2"
    assert record.extension == "fb2"
    assert record.directories == ["warhammer 40k", "dark angels"]
    assert record.source == "file"


def test_file_without_extension(tmp_path):
    root = tmp_path / "new_books"
    root.mkdir()

    file_path = root / "README"
    file_path.write_text("dummy")

    record = scan_file(str(file_path), str(root))

    assert record.extension == ""


def test_file_outside_root(tmp_path):
    root = tmp_path / "new_books"
    root.mkdir()

    outside_file = tmp_path / "book.fb2"
    outside_file.write_text("dummy")

    with pytest.raises(ValueError):
        scan_file(str(outside_file), str(root))
