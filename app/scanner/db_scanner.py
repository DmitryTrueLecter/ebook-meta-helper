"""Scanner that populates the database with directory and file records."""

from __future__ import annotations

import hashlib
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from db.models.directory import Directory
from db.models.file_record import FileRecord


SUPPORTED_EXTENSIONS = {"epub", "fb2", "mobi", "azw3", "pdf", "djvu"}
HASH_CHUNK_SIZE = 8192

def extract_sort_order(filename: str) -> Optional[float]:
    """Extract numeric sort order from filename.
    
    Looks for leading numbers or common patterns like:
    - "01 - Title.epub" -> 1.0
    - "Book 3 - Title.fb2" -> 3.0
    - "Chapter_05.epub" -> 5.0
    - "1.5 - Interlude.epub" -> 1.5
    """
    import re
    
    name = Path(filename).stem
    
    # Leading number: "01 - Title", "1. Chapter", "05_name"
    match = re.match(r'^(\d+(?:\.\d+)?)', name)
    if match:
        return float(match.group(1))
    
    # Hash prefix: "#3 Title"
    match = re.match(r'^#\s*(\d+(?:\.\d+)?)', name)
    if match:
        return float(match.group(1))
    
    # Number in brackets/parentheses at start: "[01]", "(3)"
    match = re.match(r'^[\[\(](\d+(?:\.\d+)?)[\]\)]', name)
    if match:
        return float(match.group(1))
    
    # Number after common prefixes: "Book 3", "Chapter 5", "Part 2", "chapter_12"
    match = re.search(r'(?:book|chapter|part|vol|volume|tome)[\s_]*(\d+(?:\.\d+)?)', name, re.IGNORECASE)
    if match:
        return float(match.group(1))
    
    return None


def detect_format(path: Path) -> Optional[str]:
    """Detect file format and version by content analysis."""
    try:
        with open(path, "rb") as f:
            header = f.read(1024)
    except Exception:
        return None
    
    if not header:
        return None
    
    # PDF - version in header: %PDF-1.4, %PDF-1.7, %PDF-2.0
    if header.startswith(b"%PDF-"):
        return _detect_pdf_version(header)
    
    # DJVU
    if header.startswith(b"AT&TFORM"):
        return "DJVU"
    
    # ZIP-based (EPUB, etc.)
    if header.startswith(b"PK\x03\x04"):
        return _detect_epub_version(path)
    
    # XML-based (FB2)
    if header.startswith(b"<?xml") or header.startswith(b"\xef\xbb\xbf<?xml"):
        return _detect_fb2_version(path, header)
    
    # MOBI/AZW
    palm_type = header[60:68] if len(header) >= 68 else b""
    if palm_type == b"BOOKMOBI":
        return _detect_mobi_version(header)
    if palm_type == b"TEXtREAd":
        return "PalmDOC"
    
    return None


def _detect_pdf_version(header: bytes) -> str:
    """Extract PDF version from header."""
    # %PDF-1.4, %PDF-1.7, %PDF-2.0
    try:
        version_end = header.index(b"\n", 5)
        version_str = header[5:version_end].decode("ascii").strip()
        return f"PDF {version_str}"
    except Exception:
        return "PDF"


def _detect_epub_version(path: Path) -> Optional[str]:
    """Detect EPUB version from OPF package."""
    import re
    
    try:
        with zipfile.ZipFile(path, "r") as zf:
            namelist = zf.namelist()
            
            # Check mimetype
            if "mimetype" in namelist:
                mimetype = zf.read("mimetype").decode("utf-8", errors="ignore").strip()
                if "epub" not in mimetype.lower():
                    return None
            elif "META-INF/container.xml" not in namelist:
                return None
            
            # Find OPF file from container.xml
            opf_path = None
            if "META-INF/container.xml" in namelist:
                container = zf.read("META-INF/container.xml").decode("utf-8", errors="ignore")
                match = re.search(r'full-path="([^"]+)"', container)
                if match:
                    opf_path = match.group(1)
            
            # Try common OPF locations
            if not opf_path or opf_path not in namelist:
                for candidate in namelist:
                    if candidate.endswith(".opf"):
                        opf_path = candidate
                        break
            
            if opf_path and opf_path in namelist:
                opf_content = zf.read(opf_path).decode("utf-8", errors="ignore")
                
                # <package version="3.0" or version="2.0"
                match = re.search(r'<package[^>]+version=["\']([^"\']+)["\']', opf_content)
                if match:
                    return f"EPUB {match.group(1)}"
                
                # No version attribute - check for EPUB3 indicators
                # EPUB3 uses "http://www.idpf.org/2007/ops" for content
                # and has properties like "nav", "cover-image" etc.
                if 'epub:type=' in opf_content or 'properties="nav"' in opf_content:
                    return "EPUB 3.0"
                
                # Check for dc-metadata (EPUB 2.0 style)
                if '<dc-metadata' in opf_content or 'http://purl.org/dc/elements/1.0/' in opf_content:
                    return "EPUB 2.0"
                
                # Default: if package exists but no version, likely EPUB 2.0
                if '<package' in opf_content:
                    return "EPUB 2.0"
            
            # Has container.xml or mimetype but couldn't determine version
            return "EPUB 2.0"
    except Exception:
        return None


def _detect_fb2_version(path: Path, header: bytes) -> Optional[str]:
    """Detect FB2 version from namespace."""
    try:
        with open(path, "rb") as f:
            content = f.read(4096).decode("utf-8", errors="ignore")
        
        if "FictionBook" not in content and "fictionbook" not in content.lower():
            return None
        
        import re
        # xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"
        # xmlns="http://www.gribuser.ru/xml/fictionbook/2.1"
        match = re.search(r'fictionbook/(\d+\.\d+)', content, re.IGNORECASE)
        if match:
            return f"FB2 {match.group(1)}"
        
        return "FB2"
    except Exception:
        return None


def _detect_mobi_version(header: bytes) -> str:
    """Detect MOBI version/type from header."""
    # MOBI header at offset 78-80 contains version
    if len(header) >= 80:
        mobi_type = int.from_bytes(header[78:80], "big")
        if mobi_type == 2:
            return "MOBI"
        elif mobi_type == 3:
            return "PalmDOC"
        elif mobi_type == 232:
            return "KF8"  # Kindle Format 8 (AZW3)
        elif mobi_type == 248:
            return "KF8"
    return "MOBI"


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(HASH_CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_or_create_directory(
    session: Session,
    path: Path,
    parent: Optional[Directory] = None,
    cache: Optional[dict[str, Directory]] = None,
) -> Directory:
    """Get existing directory or create a new one.
    
    Uses cache to avoid repeated DB lookups within the same scan session.
    """
    path_str = str(path)
    
    if cache is not None and path_str in cache:
        return cache[path_str]
    
    existing = session.query(Directory).filter(Directory.path == path_str).first()
    if existing:
        if cache is not None:
            cache[path_str] = existing
        return existing
    
    directory = Directory(
        path=path_str,
        name=path.name,
        parent_id=parent.id if parent else None,
    )
    session.add(directory)
    session.flush()
    
    if cache is not None:
        cache[path_str] = directory
    
    return directory


def ensure_directory_hierarchy(
    session: Session,
    target_path: Path,
    root_path: Path,
    cache: Optional[dict[str, Directory]] = None,
) -> Directory:
    """Ensure all directories in the path exist, creating missing ones.
    
    Returns the Directory record for target_path.
    """
    try:
        relative = target_path.relative_to(root_path)
    except ValueError:
        raise ValueError(f"Target path {target_path} is not under root {root_path}")
    
    current_path = root_path
    parent: Optional[Directory] = None
    
    parts = [root_path.name] + list(relative.parts)
    
    for i, part in enumerate(parts):
        if i == 0:
            current_path = root_path
        else:
            current_path = current_path / part
        
        parent = get_or_create_directory(session, current_path, parent, cache)
    
    return parent


def scan_file_to_db(
    session: Session,
    file_path: Path,
    directory: Directory,
) -> Optional[FileRecord]:
    """Create or update a FileRecord for the given file.
    
    Returns None if file doesn't exist or can't be read.
    """
    if not file_path.is_file():
        return None
    
    filename = file_path.name
    file_format = detect_format(file_path)
    sort_order = extract_sort_order(filename)
    
    stat = file_path.stat()
    size = stat.st_size
    modified_at = datetime.fromtimestamp(stat.st_mtime)
    
    existing = (
        session.query(FileRecord)
        .filter(
            FileRecord.directory_id == directory.id,
            FileRecord.filename == filename,
        )
        .first()
    )
    
    if existing:
        need_update = (
            existing.size != size
            or existing.file_modified_at != modified_at
            or existing.format != file_format
            or existing.sort_order != sort_order
        )
        if not need_update:
            return existing
        
        file_hash = compute_file_hash(file_path)
        existing.size = size
        existing.hash = file_hash
        existing.format = file_format
        existing.sort_order = sort_order
        existing.file_modified_at = modified_at
        session.flush()
        return existing
    
    file_hash = compute_file_hash(file_path)
    
    record = FileRecord(
        directory_id=directory.id,
        filename=filename,
        format=file_format,
        sort_order=sort_order,
        size=size,
        hash=file_hash,
        file_modified_at=modified_at,
    )
    session.add(record)
    session.flush()
    
    return record


class DBScanner:
    """Scanner that populates database with directory and file records."""
    
    def __init__(
        self,
        session: Session,
        extensions: Optional[set[str]] = None,
        verbose: bool = False,
    ):
        self.session = session
        self.extensions = extensions or SUPPORTED_EXTENSIONS
        self.verbose = verbose
        self._dir_cache: dict[str, Directory] = {}
        
        self.stats = {
            "directories_created": 0,
            "directories_existing": 0,
            "files_created": 0,
            "files_updated": 0,
            "files_skipped": 0,
            "errors": 0,
        }
    
    def log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
    
    def scan(self, root_dir: str) -> dict:
        """Scan directory tree and populate database.
        
        Args:
            root_dir: Path to the root directory to scan.
            
        Returns:
            Statistics dictionary with counts of created/updated records.
        """
        root = Path(root_dir).resolve()
        
        if not root.exists():
            raise ValueError(f"Directory does not exist: {root}")
        
        if not root.is_dir():
            raise ValueError(f"Path is not a directory: {root}")
        
        self.log(f"Scanning: {root}")
        
        root_dir_record = get_or_create_directory(
            self.session, root, None, self._dir_cache
        )
        root_dir_record.last_scanned_at = datetime.now()
        
        for item in root.rglob("*"):
            if item.is_dir():
                self._process_directory(item, root)
            elif item.is_file():
                self._process_file(item, root)
        
        self.session.flush()
        
        return self.stats.copy()
    
    def _process_directory(self, dir_path: Path, root: Path) -> None:
        """Process a single directory."""
        path_str = str(dir_path)
        
        if path_str in self._dir_cache:
            self.stats["directories_existing"] += 1
            return
        
        try:
            ensure_directory_hierarchy(
                self.session, dir_path, root, self._dir_cache
            )
            self.stats["directories_created"] += 1
            self.log(f"  DIR: {dir_path.relative_to(root)}")
        except Exception as e:
            self.stats["errors"] += 1
            self.log(f"  ERROR (dir): {dir_path} - {e}")
    
    def _process_file(self, file_path: Path, root: Path) -> None:
        """Process a single file."""
        extension = file_path.suffix.lstrip(".").lower()
        
        if extension not in self.extensions:
            self.stats["files_skipped"] += 1
            return
        
        try:
            directory = ensure_directory_hierarchy(
                self.session, file_path.parent, root, self._dir_cache
            )
            
            existing = (
                self.session.query(FileRecord)
                .filter(
                    FileRecord.directory_id == directory.id,
                    FileRecord.filename == file_path.name,
                )
                .first()
            )
            
            record = scan_file_to_db(self.session, file_path, directory)
            
            if record:
                if existing:
                    self.stats["files_updated"] += 1
                    self.log(f"  UPD: {file_path.relative_to(root)}")
                else:
                    self.stats["files_created"] += 1
                    self.log(f"  NEW: {file_path.relative_to(root)}")
        except Exception as e:
            self.stats["errors"] += 1
            self.log(f"  ERROR (file): {file_path} - {e}")


def scan_directory_to_db(
    session: Session,
    root_dir: str,
    extensions: Optional[set[str]] = None,
    verbose: bool = False,
) -> dict:
    """Convenience function to scan a directory and populate the database.
    
    Args:
        session: SQLAlchemy session.
        root_dir: Path to the root directory.
        extensions: Set of file extensions to include (without dot).
        verbose: Print progress messages.
        
    Returns:
        Statistics dictionary.
    """
    scanner = DBScanner(session, extensions, verbose)
    return scanner.scan(root_dir)
