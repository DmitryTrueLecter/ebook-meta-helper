#!/usr/bin/env python
"""Scan NEW_BOOKS_DIR and populate the database."""

from dotenv import load_dotenv

load_dotenv()

import os
import sys

from db.session import get_session
from app.scanner.db_scanner import scan_directory_to_db, SUPPORTED_EXTENSIONS


def main() -> None:
    new_books_dir = os.environ.get("NEW_BOOKS_DIR")
    if not new_books_dir:
        print("Error: NEW_BOOKS_DIR not set in .env", file=sys.stderr)
        sys.exit(1)
    
    print(f"Scanning: {new_books_dir}")
    
    with get_session() as session:
        stats = scan_directory_to_db(session, new_books_dir, verbose=True)
    
    print()
    print("Scan complete:")
    print(f"  Directories created: {stats['directories_created']}")
    print(f"  Files created: {stats['files_created']}")
    print(f"  Files updated: {stats['files_updated']}")
    print(f"  Files skipped: {stats['files_skipped']}")
    if stats["errors"] > 0:
        print(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
