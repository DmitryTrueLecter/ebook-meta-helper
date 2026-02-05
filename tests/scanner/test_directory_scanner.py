from scanner.directory_scanner import scan_directory


def test_empty_directory(tmp_path):
    root = tmp_path / "new_books"
    root.mkdir()

    records = scan_directory(str(root))

    assert records == []


def test_nested_directories(tmp_path):
    root = tmp_path / "new_books"
    book_dir = root / "warhammer 40k" / "dark angels"
    book_dir.mkdir(parents=True)

    f1 = book_dir / "book1.fb2"
    f2 = book_dir / "book2.epub"

    f1.write_text("dummy")
    f2.write_text("dummy")

    records = scan_directory(str(root))

    assert len(records) == 2
    filenames = {r.original_filename for r in records}
    assert filenames == {"book1.fb2", "book2.epub"}


def test_files_in_root(tmp_path):
    root = tmp_path / "new_books"
    root.mkdir()

    f = root / "root_book.pdf"
    f.write_text("dummy")

    records = scan_directory(str(root))

    assert len(records) == 1
    assert records[0].directories == []


def test_nonexistent_root(tmp_path):
    missing = tmp_path / "missing"

    try:
        scan_directory(str(missing))
    except ValueError as e:
        assert "does not exist" in str(e)
    else:
        assert False, "Expected ValueError"
