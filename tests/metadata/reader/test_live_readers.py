from pathlib import Path
import json
import pytest
from models.book import BookRecord
from metadata.reader.registry import read_metadata


def run_live_test(asset_folder: str):
    folder = Path(__file__).parent.parent.parent / "assets" / asset_folder
    for file in folder.glob("*.*"):
        if file.suffix.lower() == ".json":
            continue

        json_file = file.with_suffix(".json")
        if not json_file.exists():
            raise ValueError(f"Expected metadata JSON missing for {file.name}")

        expected = json.loads(json_file.read_text(encoding="utf-8"))

        record = BookRecord(
            path=str(file),
            original_filename=file.name,
            extension=file.suffix.lstrip("."),
            directories=[]
        )

        record = read_metadata(record)

        errors = []
        for key, value in expected.items():
            record_value = getattr(record, key, None)
            if record_value != value:
                errors.append(f"{key} mismatch: expected {value}, got {record_value}")

        if errors:
            raise AssertionError(f"{file.name} metadata mismatches:\n" + "\n".join(errors))


def test_live_epub():
    run_live_test("epub")


def test_live_fb2():
    run_live_test("fb2")
