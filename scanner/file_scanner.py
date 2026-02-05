from pathlib import Path
from models.book import BookRecord


def scan_file(file_path: str, root_dir: str) -> BookRecord:
    file_path = Path(file_path).resolve()
    root_dir = Path(root_dir).resolve()

    try:
        relative_path = file_path.relative_to(root_dir)
    except ValueError:
        raise ValueError("File is not inside root directory")

    directories = list(relative_path.parent.parts)

    filename = file_path.name
    extension = file_path.suffix.lstrip(".") if file_path.suffix else ""

    return BookRecord(
        path=str(file_path),
        original_filename=filename,
        extension=extension,
        directories=directories,
        source="file",
    )
