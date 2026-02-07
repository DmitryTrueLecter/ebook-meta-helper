from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from models.book import BookRecord


@dataclass
class PipelineResult:
    success: bool
    record: Optional[BookRecord] = None
    final_path: Optional[Path] = None
    errors: List[str] = field(default_factory=list)
