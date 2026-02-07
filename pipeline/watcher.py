import os
import time
from typing import List

from dotenv import load_dotenv

from models.book import BookRecord
from pipeline.process_file import process_file
from scanner.directory_scanner import scan_directory


def run_watcher() -> None:
    load_dotenv()

    new_books_dir = os.environ.get("NEW_BOOKS_DIR")
    if not new_books_dir:
        raise RuntimeError("NEW_BOOKS_DIR is not set")

    sleep_seconds = int(os.environ.get("WATCH_SLEEP_SECONDS", "10"))

    print(f"[watcher] watching NEW_BOOKS_DIR: {new_books_dir}")
    print(f"[watcher] sleep when idle: {sleep_seconds}s")

    while True:
        try:
            records: List[BookRecord] = scan_directory(new_books_dir)
        except Exception as e:
            print(f"[watcher] scan error: {e}")
            time.sleep(sleep_seconds)
            continue

        if not records:
            time.sleep(sleep_seconds)
            continue

        for record in records:
            try:
                print(f"[watcher] processing: {record.path}")
                result = process_file(record)

                if result.success:
                    print(f"[watcher] OK: {record.path}")
                else:
                    print(f"[watcher] FAILED: {record.path}")
                    for err in result.errors:
                        print(f"  - {err}")

            except Exception as e:
                print(f"[watcher] unexpected error for {record.path}: {e}")

        time.sleep(1)
