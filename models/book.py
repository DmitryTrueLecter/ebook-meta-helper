from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date


@dataclass
class OriginalWork:
    title: Optional[str] = None
    language: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None


@dataclass
class BookRecord:
    # File info
    path: str
    original_filename: str
    extension: str
    directories: List[str]

    # Local / edition metadata
    title: Optional[str] = None
    subtitle: Optional[str] = None
    authors: List[str] = field(default_factory=list)

    series: Optional[str] = None
    series_index: Optional[int] = None
    series_total: Optional[int] = None

    language: Optional[str] = None

    publisher: Optional[str] = None

    # Identifiers
    isbn10: Optional[str] = None
    isbn13: Optional[str] = None
    asin: Optional[str] = None

    # Dates
    published: Optional[date] = None
    year: Optional[int] = None  # legacy / fallback

    # Original work metadata
    original: Optional[OriginalWork] = None

    # Provenance
    source: Optional[str] = None
    confidence: Optional[float] = None

    # Technical
    errors: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
