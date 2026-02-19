import json
from datetime import datetime
from typing import Any, Dict, Tuple, List

from ai.contracts.schema_loader import (
    get_edition_fields,
    get_original_fields,
    get_confidence_field,
    validate_field_value,
)


def parse_book_metadata(raw: Any) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parse AI response into structured metadata.
    Uses schema from book_metadata.v1.json for field definitions.
    """
    errors: List[str] = []

    # --- Load JSON ---
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            return {}, [f"invalid json: {e}"]
    elif isinstance(raw, dict):
        data = raw
    else:
        return {}, ["response is neither json string nor dict"]

    if not isinstance(data, dict):
        return {}, ["top-level json is not an object"]

    parsed: Dict[str, Any] = {}

    # --- Edition (dynamically from schema) ---
    edition = data.get("edition")
    if edition is not None:
        if not isinstance(edition, dict):
            errors.append("edition must be an object")
        else:
            edition_fields = get_edition_fields()
            parsed_edition = _parse_section(
                edition,
                edition_fields,
                "edition",
                errors
            )
            if parsed_edition:
                parsed["edition"] = parsed_edition

    # --- Original (dynamically from schema) ---
    original = data.get("original")
    if original is not None:
        if not isinstance(original, dict):
            errors.append("original must be an object")
        else:
            original_fields = get_original_fields()
            parsed_original = _parse_section(
                original,
                original_fields,
                "original",
                errors
            )
            if parsed_original:
                parsed["original"] = parsed_original

    # --- Confidence ---
    confidence = data.get("confidence")
    if confidence is not None:
        conf_field = get_confidence_field()
        if validate_field_value(confidence, conf_field):
            # Check range if specified
            conf_range = conf_field.get("range")
            if conf_range:
                if conf_range[0] <= float(confidence) <= conf_range[1]:
                    parsed["confidence"] = float(confidence)
                else:
                    errors.append(f"confidence out of range {conf_range}")
            else:
                parsed["confidence"] = float(confidence)
        else:
            errors.append("confidence must be a number")

    return parsed, errors


def _parse_section(
    data_section: Dict[str, Any],
    schema_fields: Dict[str, Dict[str, Any]],
    section_name: str,
    errors: List[str]
) -> Dict[str, Any]:
    """Parse a section (edition or original) using schema definitions"""
    parsed = {}

    for field_name, field_def in schema_fields.items():
        if field_name not in data_section:
            continue

        value = data_section[field_name]

        # Validate type
        if not validate_field_value(value, field_def):
            errors.append(f"{section_name}.{field_name} has invalid type")
            continue

        # Special handling for date fields
        type_str = field_def.get("type", "string")
        if type_str == "date" and isinstance(value, str):
            try:
                parsed[field_name] = datetime.fromisoformat(value).date()
            except ValueError:
                errors.append(f"{section_name}.{field_name} invalid ISO date: {value}")
                continue
        else:
            parsed[field_name] = value

    return parsed
