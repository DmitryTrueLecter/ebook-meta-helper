from pathlib import Path
import re


class MoveError(Exception):
    pass


# Characters illegal in Windows filenames
_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|]')


def sanitize_filename(filename: str) -> str:
    """Replace illegal Windows filename characters with safe alternatives."""
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    stem = _ILLEGAL_CHARS.sub("-", stem)
    # Collapse multiple consecutive dashes and strip leading/trailing whitespace/dots
    stem = re.sub(r"-{2,}", "-", stem).strip(" .")
    return stem + suffix


def move_file(
    src: Path,
    dst_dir: Path,
    filename: str,
    subdirs: list[str] | None = None,
) -> Path:
    if not src.exists():
        raise MoveError(f"source file does not exist: {src}")

    if not src.is_file():
        raise MoveError(f"source is not a file: {src}")

    # Preserve subdirectory structure from BookRecord.directories
    if subdirs:
        target_dir = dst_dir.joinpath(*subdirs)
    else:
        target_dir = dst_dir

    target_dir.mkdir(parents=True, exist_ok=True)

    filename = sanitize_filename(filename)
    target = target_dir / filename

    # Overwrite existing file if present
    if target.exists():
        target.unlink()

    src.rename(target.resolve())
    return target