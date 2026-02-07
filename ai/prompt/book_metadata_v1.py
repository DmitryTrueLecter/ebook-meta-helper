from models.book import BookRecord
from ai.contracts.schema_loader import (
    get_edition_fields,
    get_original_fields,
    get_confidence_field,
    get_prompt_label,
    get_ai_hint,
    get_field_type,
    get_rules,
)


def build_book_metadata_prompt(record: BookRecord) -> str:
    """
    Build prompt for AI to enrich book metadata.
    Output MUST be valid JSON according to book_metadata_v1 contract.
    Uses schema from book_metadata.v1.json for field definitions.
    """

    lines: list[str] = []

    lines.append(
        "You are a bibliographic metadata extraction engine."
    )

    lines.append(
        "Given partial information about a book file, "
        "identify the most likely edition and its original work."
    )

    lines.append("\nKnown file context:")

    lines.append(f"- Filename: {record.original_filename}")
    lines.append(f"- Extension: {record.extension}")

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

    # --- Instructions ---
    lines.append(
        "\nInstructions:\n"
        "- Respond ONLY with valid JSON\n"
        "- Do NOT include explanations or comments\n"
        "- Omit unknown fields\n"
        "- Use UTF-8\n"
    )

    # Add schema rules
    rules = get_rules()
    for rule in rules:
        lines.append(f"- {rule}")

    # --- Contract (dynamically from schema) ---
    lines.append("\nJSON format (book_metadata_v1):")
    lines.append("{")

    # Edition section
    lines.append('  "edition": {')
    for field_name, field_def in edition_fields.items():
        type_str = get_field_type(field_def)
        hint = get_ai_hint(field_def)
        lines.append(f'    "{field_name}": {type_str},  // {hint}')
    lines.append("  },")

    # Original section
    lines.append('  "original": {')
    for field_name, field_def in original_fields.items():
        type_str = get_field_type(field_def)
        hint = get_ai_hint(field_def)
        lines.append(f'    "{field_name}": {type_str},  // {hint}')
    lines.append("  },")

    # Confidence
    conf_field = get_confidence_field()
    conf_type = get_field_type(conf_field)
    conf_hint = get_ai_hint(conf_field)
    lines.append(f'  "confidence": {conf_type}  // {conf_hint}')

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
