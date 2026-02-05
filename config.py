import os

NEW_BOOKS_DIR = os.getenv("NEW_BOOKS_DIR")
BOOKS_READY_DIR = os.getenv("BOOKS_READY_DIR")

if not NEW_BOOKS_DIR or not BOOKS_READY_DIR:
    raise RuntimeError("Required environment variables are not set")
