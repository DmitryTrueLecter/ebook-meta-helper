import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from ai.enrich import enrich
from metadata import read_metadata
from models.book import BookRecord
from scanner.directory_scanner import scan_directory
from utils.debug import Debugger


def run_debug() -> None:
    load_dotenv()

    new_books_dir = os.environ.get("NEW_BOOKS_DIR")
    if not new_books_dir:
        raise RuntimeError("NEW_BOOKS_DIR is not set")

    records: List[BookRecord] = scan_directory(new_books_dir)

    for record in records:
        try:
            print(f"[watcher] processing: {record.path}")
            process_file_debug(record)

        except Exception as e:
            print(f"[watcher] unexpected error for {record.path}: {e}")

def process_file_debug(record: BookRecord) -> None:
    path = Path(record.path)
    debugger = Debugger(path)
    errors: list[str] = []

    debugger.log("init", "input BookRecord from scanner", record)

    records = [record]

    # 2. Read embedded metadata
    try:
        record_with_meta = read_metadata(record)
        debugger.log("read_metadata", "metadata read from file", record_with_meta)
        records.append(record_with_meta)
    except Exception as e:
        errors.append(f"read_metadata: {e}")
        debugger.log("read_metadata_error", str(e), record)

    # 3. AI enrichment
    try:
        ai_provider = os.getenv("AI_PROVIDER")
        ai_record = enrich(record, ai_provider)
        debugger.log("ai_enrich", "AI metadata enrichment", ai_record)
        records.append(ai_record)
    except Exception as e:
        errors.append(f"ai_enrich: {e}")
        debugger.log("ai_enrich_error", str(e), record)



if __name__ == "__main__":
    run_debug()