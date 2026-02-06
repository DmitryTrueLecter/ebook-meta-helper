from dataclasses import dataclass, field
from typing import List, Optional


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

    # Local / edition metadata (what THIS file represents)
    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    series: Optional[str] = None
    series_index: Optional[int] = None
    language: Optional[str] = None
    year: Optional[int] = None

    # Original work metadata
    original: Optional[OriginalWork] = None

    # Provenance
    source: Optional[str] = None
    confidence: Optional[float] = None

    # Technical
    errors: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
