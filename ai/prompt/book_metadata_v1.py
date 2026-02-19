import json
from pathlib import Path

from models.book import BookRecord
from ai.contracts.schema_loader import (
    get_edition_fields,
    get_original_fields,
    get_prompt_label,
)

def build_system_prompt() -> str:
    lines: list[str] = []
    lines.append(
        "You are a bibliographic metadata extractor. Given a book file path and partial metadata, identify the complete bibliographic information. "
        "Field priority: "
        "Author and title must match exactly (allow transliteration for translations) "
        "Directory path and filename provide context: may contain author, universe, series/subseries "
        "Rules: "
        "If translated (e.g., to Russian), find both translated and original edition metadata "
        "Never substitute a different author, even for more famous works with same title "
        "When titles collide, prefer the match consistent with directory context "
        "Don't fabricate metadata when evidence is insufficient "
        "Determine work type (novel, story, novella, poem, etc.) "
        "Provide a non-creative book description based on known publisher or catalog summaries. "
        "Do not invent plot details. "
        "If the book is well known, provide its commonly published summary. "
        "If insufficient information is available, return null in the description field. "
        "Keep the description factual and neutral. "
    )
    return "\n". join(lines)

def get_response_format() -> str:
    schema_path = Path(__file__).parent / "../contracts/book_metadata.v2.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_book_metadata_prompt(record: BookRecord) -> str:
    """
    Build prompt for AI to enrich book metadata.
    Output MUST be valid JSON according to book_metadata_v1 contract.
    Uses schema from book_metadata.v1.json for field definitions.
    """

    lines: list[str] = []

    lines.append("\nKnown file context:")

    lines.append(f"- Filename: {record.original_filename}")

    if record.directories:
        lines.append(
            "- Directory context: "
            + " / ".join(record.directories)
        )

    # --- Existing edition (dynamically from schema) ---
    edition_fields = get_edition_fields()
    edition_values = _extract_edition_values(record, edition_fields)

    if edition_values:
        lines.append("\nExisting edition metadata:")
        for field_name, field_def in edition_fields.items():
            value = edition_values.get(field_name)
            if value is not None:
                label = get_prompt_label(field_def)
                if isinstance(value, list):
                    lines.append(f"- {label}: {', '.join(str(v) for v in value)}")
                else:
                    lines.append(f"- {label}: {value}")

    # --- Existing original (dynamically from schema) ---
    original_fields = get_original_fields()
    if record.original:
        original_values = _extract_original_values(record, original_fields)

        if original_values:
            lines.append("\nExisting original work metadata:")
            for field_name, field_def in original_fields.items():
                value = original_values.get(field_name)
                if value is not None:
                    label = get_prompt_label(field_def)
                    if isinstance(value, list):
                        lines.append(f"- {label}: {', '.join(str(v) for v in value)}")
                    else:
                        lines.append(f"- {label}: {value}")

    lines.append("}")

    return "\n".join(lines)

def _extract_edition_values(record: BookRecord, edition_fields: dict) -> dict:
    """Extract edition values from BookRecord based on schema fields"""
    values = {}

    for field_name in edition_fields.keys():
        value = getattr(record, field_name, None)
        if value is not None:
            # Skip empty lists
            if isinstance(value, list) and len(value) == 0:
                continue
            values[field_name] = value

    return values

def _extract_original_values(record: BookRecord, original_fields: dict) -> dict:
    """Extract original work values from BookRecord based on schema fields"""
    if not record.original:
        return {}

    values = {}

    for field_name in original_fields.keys():
        value = getattr(record.original, field_name, None)
        if value is not None:
            # Skip empty lists
            if isinstance(value, list) and len(value) == 0:
                continue
            values[field_name] = value

    return values
