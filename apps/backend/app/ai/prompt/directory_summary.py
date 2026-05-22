"""Prompt and response-format for AIProvider.summarize_directory()."""

from typing import Any, Optional

from app.models.book import BookRecord


SUMMARY_KEYS = (
    "series_name",
    "universe",
    "genre",
    "tags",
    "language",
    "confidence",
    "notes",
)


def build_directory_summary_system_prompt() -> str:
    return (
        "You are a bibliographic collection analyser. Given a list of ebook "
        "filenames from a single directory (and the directory path itself), "
        "produce a high-level summary describing what the collection appears "
        "to contain. Do not invent facts — when evidence is insufficient, use "
        "null or an empty list and lower the confidence value. The summary is "
        "passed back to a per-file enrichment step as upstream context, so it "
        "must capture properties shared across the collection: series, "
        "universe, dominant genre, common language, and reusable tags. "
        "Do not list per-book details (titles, individual authors) here."
    )


def build_directory_summary_user_prompt(files: list[BookRecord]) -> str:
    lines: list[str] = []

    directories = _common_directory_path(files)
    if directories:
        lines.append(f"Directory path: {' / '.join(directories)}")

    lines.append(f"File count: {len(files)}")
    lines.append("")
    lines.append("Filenames:")
    for record in files:
        lines.append(f"- {record.original_filename}")

    return "\n".join(lines)


def get_directory_summary_response_format() -> dict:
    """JSON-mode response format for the OpenAI Responses API."""
    return {
        "type": "json_schema",
        "name": "directory_summary",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "series_name": {
                    "type": ["string", "null"],
                    "description": (
                        "Common book series name across the collection; "
                        "null if the directory does not represent a single series."
                    ),
                },
                "universe": {
                    "type": ["string", "null"],
                    "description": (
                        "Shared fictional universe or franchise "
                        "(e.g. 'Warhammer 40k'); null if not applicable."
                    ),
                },
                "genre": {
                    "type": ["string", "null"],
                    "description": "Dominant genre across the collection; null if mixed.",
                },
                "tags": {
                    "type": "array",
                    "description": "Reusable normalised tags shared by most files.",
                    "items": {"type": "string"},
                },
                "language": {
                    "type": ["string", "null"],
                    "description": (
                        "Dominant language as ISO 639-1 code; null if mixed or unknown."
                    ),
                },
                "confidence": {
                    "type": "number",
                    "description": "Overall confidence in the summary, 0.0 to 1.0.",
                    "minimum": 0,
                    "maximum": 1,
                },
                "notes": {
                    "type": ["string", "null"],
                    "description": "Short free-form remarks about the collection; null if none.",
                },
            },
            "required": list(SUMMARY_KEYS),
            "additionalProperties": False,
        },
    }


def empty_summary() -> dict:
    """The canonical 'no information' summary; used as the fallback shape."""
    return {
        "series_name": None,
        "universe": None,
        "genre": None,
        "tags": [],
        "language": None,
        "confidence": 0.0,
        "notes": None,
    }


def normalize_summary(raw: Any) -> dict:
    """Coerce a raw dict-shaped response into the canonical summary shape."""
    if not isinstance(raw, dict):
        return empty_summary()

    result = empty_summary()

    for key in ("series_name", "universe", "genre", "language", "notes"):
        value = raw.get(key)
        if isinstance(value, str) and value != "":
            result[key] = value

    tags = raw.get("tags")
    if isinstance(tags, list):
        result["tags"] = [t for t in tags if isinstance(t, str) and t]

    confidence = raw.get("confidence")
    if isinstance(confidence, (int, float)):
        clamped = max(0.0, min(1.0, float(confidence)))
        result["confidence"] = clamped

    return result


def format_directory_hint_for_book_prompt(hint: Optional[dict]) -> str:
    """Render a directory hint as a context block; empty string when no information."""
    if not hint:
        return ""

    fields: list[tuple[str, Any]] = [
        ("Series", hint.get("series_name")),
        ("Universe", hint.get("universe")),
        ("Genre", hint.get("genre")),
        ("Tags", hint.get("tags")),
        ("Language", hint.get("language")),
    ]

    rendered: list[str] = []
    for label, value in fields:
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                continue
            rendered.append(f"{label}: {', '.join(str(v) for v in value)}")
        else:
            rendered.append(f"{label}: {value}")

    if not rendered:
        return ""

    lines = ["Context: This book is from a collection summarized as:"]
    lines.extend(rendered)
    return "\n".join(lines)


def _common_directory_path(files: list[BookRecord]) -> list[str]:
    """Longest common prefix of the per-file `directories` lists."""
    if not files:
        return []

    common = list(files[0].directories)
    for record in files[1:]:
        new_common: list[str] = []
        for left, right in zip(common, record.directories):
            if left == right:
                new_common.append(left)
            else:
                break
        common = new_common
        if not common:
            break

    return common
