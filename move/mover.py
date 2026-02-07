from datetime import datetime
from pathlib import Path


class MoveError(Exception):
    pass


def move_file(
    src: Path,
    dst_dir: Path,
    filename: str,
) -> Path:
    if not src.exists():
        raise MoveError(f"source file does not exist: {src}")

    if not src.is_file():
        raise MoveError(f"source is not a file: {src}")

    dst_dir.mkdir(parents=True, exist_ok=True)

    target = dst_dir / filename

    if not target.exists():
        src.rename(target)
        return target

    target = _resolve_collision(target)
    src.rename(target)
    return target


def _resolve_collision(base: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    stem = base.stem
    suffix = base.suffix
    parent = base.parent

    counter = 1
    while True:
        candidate = parent / f"{stem}_v{timestamp}_v{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
