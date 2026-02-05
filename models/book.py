from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BookRecord:
    # File info
    path: str
    original_filename: str
    extension: str
    directories: List[str]

    # Metadata
    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    series: Optional[str] = None
    series_index: Optional[int] = None
    language: Optional[str] = None
    year: Optional[int] = None

    # Provenance
    source: Optional[str] = None      # "file", "ai", "mixed"
    confidence: Optional[float] = None

    # Technical
    errors: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
