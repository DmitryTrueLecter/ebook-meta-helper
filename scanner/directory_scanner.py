from pathlib import Path
from typing import List

from scanner.file_scanner import scan_file
from models.book import BookRecord


def scan_directory(root_dir: str) -> List[BookRecord]:
    root = Path(root_dir).resolve()

    if not root.exists():
        raise ValueError("Root directory does not exist")

    if not root.is_dir():
        raise ValueError("Root path is not a directory")

    records: List[BookRecord] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        record = scan_file(str(path), str(root))
        records.append(record)

    return records
