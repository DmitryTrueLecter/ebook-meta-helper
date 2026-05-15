"""Tests for database scanner functionality."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.scanner.db_scanner import (
    compute_file_hash,
    detect_format,
    extract_sort_order,
    get_or_create_directory,
    ensure_directory_hierarchy,
    scan_file_to_db,
    DBScanner,
    scan_directory_to_db,
)
from db.models.directory import Directory
from db.models.file_record import FileRecord


class TestExtractSortOrder:
    def test_leading_number(self):
        assert extract_sort_order("01 - Title.epub") == 1.0
        assert extract_sort_order("5 Chapter.fb2") == 5.0
        assert extract_sort_order("123_name.pdf") == 123.0
    
    def test_leading_decimal(self):
        assert extract_sort_order("1.5 - Interlude.epub") == 1.5
        assert extract_sort_order("2.0 Title.fb2") == 2.0
    
    def test_book_prefix(self):
        assert extract_sort_order("Book 3 - Title.epub") == 3.0
        assert extract_sort_order("book3.fb2") == 3.0
    
    def test_chapter_prefix(self):
        assert extract_sort_order("Chapter 5 - Name.epub") == 5.0
        assert extract_sort_order("chapter_12.fb2") == 12.0
    
    def test_volume_prefix(self):
        assert extract_sort_order("Vol 2 - Title.epub") == 2.0
        assert extract_sort_order("Volume 7.fb2") == 7.0
    
    def test_hash_prefix(self):
        assert extract_sort_order("#3 Title.epub") == 3.0
    
    def test_brackets(self):
        assert extract_sort_order("[01] Title.epub") == 1.0
        assert extract_sort_order("(5) Name.fb2") == 5.0
    
    def test_no_number(self):
        assert extract_sort_order("Just a Title.epub") is None
        assert extract_sort_order("Name.fb2") is None


class TestDetectFormat:
    def test_detect_pdf_with_version(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"%PDF-1.4\nsome content")
        
        assert detect_format(f) == "PDF 1.4"
    
    def test_detect_pdf_17(self, tmp_path):
        f = tmp_path / "test.pdf"
        f.write_bytes(b"%PDF-1.7\nsome content")
        
        assert detect_format(f) == "PDF 1.7"
    
    def test_detect_fb2_with_version(self, tmp_path):
        f = tmp_path / "test.fb2"
        f.write_bytes(b'<?xml version="1.0"?><FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">')
        
        assert detect_format(f) == "FB2 2.0"
    
    def test_detect_fb2_21(self, tmp_path):
        f = tmp_path / "test.fb2"
        f.write_bytes(b'<?xml version="1.0"?><FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.1">')
        
        assert detect_format(f) == "FB2 2.1"
    
    def test_detect_fb2_with_bom(self, tmp_path):
        f = tmp_path / "test.fb2"
        f.write_bytes(b'\xef\xbb\xbf<?xml version="1.0"?><FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">')
        
        assert detect_format(f) == "FB2 2.0"
    
    def test_unknown_format(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"just some text content")
        
        assert detect_format(f) is None
    
    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty"
        f.write_bytes(b"")
        
        assert detect_format(f) is None


class TestComputeFileHash:
    def test_hash_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        
        result = compute_file_hash(f)
        
        assert len(result) == 64
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    
    def test_hash_file_with_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        
        result = compute_file_hash(f)
        
        assert len(result) == 64
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    
    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "file1.txt"
        f2 = tmp_path / "file2.txt"
        f1.write_bytes(b"test content")
        f2.write_bytes(b"test content")
        
        assert compute_file_hash(f1) == compute_file_hash(f2)
    
    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "file1.txt"
        f2 = tmp_path / "file2.txt"
        f1.write_bytes(b"content a")
        f2.write_bytes(b"content b")
        
        assert compute_file_hash(f1) != compute_file_hash(f2)


class TestGetOrCreateDirectory:
    def test_creates_new_directory(self, tmp_path, mock_session):
        path = tmp_path / "books"
        path.mkdir()
        
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        result = get_or_create_directory(mock_session, path)
        
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        added_dir = mock_session.add.call_args[0][0]
        assert added_dir.path == str(path)
        assert added_dir.name == "books"
    
    def test_returns_existing_directory(self, tmp_path, mock_session):
        path = tmp_path / "books"
        existing = Directory(id=1, path=str(path), name="books")
        mock_session.query.return_value.filter.return_value.first.return_value = existing
        
        result = get_or_create_directory(mock_session, path)
        
        assert result == existing
        mock_session.add.assert_not_called()
    
    def test_uses_cache(self, tmp_path, mock_session):
        path = tmp_path / "books"
        cached = Directory(id=1, path=str(path), name="books")
        cache = {str(path): cached}
        
        result = get_or_create_directory(mock_session, path, cache=cache)
        
        assert result == cached
        mock_session.query.assert_not_called()
    
    def test_populates_cache(self, tmp_path, mock_session):
        path = tmp_path / "books"
        path.mkdir()
        cache = {}
        
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        result = get_or_create_directory(mock_session, path, cache=cache)
        
        assert str(path) in cache


class TestEnsureDirectoryHierarchy:
    def test_creates_hierarchy(self, tmp_path, mock_session):
        root = tmp_path / "root"
        target = root / "level1" / "level2"
        root.mkdir()
        (root / "level1").mkdir()
        target.mkdir()
        
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        cache = {}
        result = ensure_directory_hierarchy(mock_session, target, root, cache)
        
        assert mock_session.add.call_count == 3
    
    def test_raises_for_path_outside_root(self, tmp_path, mock_session):
        root = tmp_path / "root"
        outside = tmp_path / "other" / "path"
        
        with pytest.raises(ValueError, match="not under root"):
            ensure_directory_hierarchy(mock_session, outside, root)


class TestDBScanner:
    def test_scan_empty_directory(self, tmp_path, mock_session):
        root = tmp_path / "empty"
        root.mkdir()
        
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        scanner = DBScanner(mock_session)
        stats = scanner.scan(str(root))
        
        assert stats["files_created"] == 0
        assert stats["errors"] == 0
    
    def test_scan_with_supported_files(self, tmp_path, mock_session):
        root = tmp_path / "books"
        root.mkdir()
        
        (root / "book1.epub").write_bytes(b"epub content")
        (root / "book2.fb2").write_bytes(b"fb2 content")
        (root / "readme.txt").write_bytes(b"text content")
        
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        scanner = DBScanner(mock_session)
        stats = scanner.scan(str(root))
        
        assert stats["files_created"] == 2
        assert stats["files_skipped"] == 1
    
    def test_scan_nested_structure(self, tmp_path, mock_session):
        root = tmp_path / "library"
        (root / "fiction" / "scifi").mkdir(parents=True)
        (root / "nonfiction").mkdir()
        
        (root / "fiction" / "scifi" / "dune.epub").write_bytes(b"content")
        (root / "nonfiction" / "history.pdf").write_bytes(b"content")
        
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        scanner = DBScanner(mock_session)
        stats = scanner.scan(str(root))
        
        assert stats["files_created"] == 2
        assert stats["directories_created"] >= 2
    
    def test_scan_nonexistent_raises(self, mock_session):
        scanner = DBScanner(mock_session)
        
        with pytest.raises(ValueError, match="does not exist"):
            scanner.scan("/nonexistent/path/12345")
    
    def test_scan_file_not_directory_raises(self, tmp_path, mock_session):
        f = tmp_path / "file.txt"
        f.write_text("content")
        
        scanner = DBScanner(mock_session)
        
        with pytest.raises(ValueError, match="not a directory"):
            scanner.scan(str(f))
    
    def test_custom_extensions(self, tmp_path, mock_session):
        root = tmp_path / "books"
        root.mkdir()
        
        (root / "doc.txt").write_bytes(b"content")
        (root / "book.epub").write_bytes(b"content")
        
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        scanner = DBScanner(mock_session, extensions={"txt"})
        stats = scanner.scan(str(root))
        
        assert stats["files_created"] == 1
        assert stats["files_skipped"] == 1
    
    def test_verbose_mode(self, tmp_path, mock_session, capsys):
        root = tmp_path / "books"
        root.mkdir()
        (root / "book.epub").write_bytes(b"content")
        
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        scanner = DBScanner(mock_session, verbose=True)
        scanner.scan(str(root))
        
        captured = capsys.readouterr()
        assert "Scanning:" in captured.out


class TestScanDirectoryToDb:
    def test_convenience_function(self, tmp_path, mock_session):
        root = tmp_path / "books"
        root.mkdir()
        (root / "test.epub").write_bytes(b"content")
        
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        stats = scan_directory_to_db(mock_session, str(root), verbose=False)
        
        assert isinstance(stats, dict)
        assert "files_created" in stats


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    return session
