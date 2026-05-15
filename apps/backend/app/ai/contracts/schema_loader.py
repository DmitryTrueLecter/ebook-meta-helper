"""
Schema loader and utilities for working with book_metadata schema.
Provides centralized access to field definitions, types, and AI hints.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime


_SCHEMA_CACHE: Optional[Dict[str, Any]] = None


def _load_schema() -> Dict[str, Any]:
    """Load schema from book_metadata.v2.json"""
    global _SCHEMA_CACHE

    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE

    schema_path = Path(__file__).parent / "book_metadata.v2.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        _SCHEMA_CACHE = json.load(f)

    return _SCHEMA_CACHE


def _get_root_schema() -> Dict[str, Any]:
    """Get the root JSON Schema object from the format wrapper."""
    return _load_schema()["format"]["schema"]


def get_schema() -> Dict[str, Any]:
    """Get full schema"""
    return _load_schema()


def get_edition_fields() -> Dict[str, Dict[str, Any]]:
    """Get edition field definitions (name -> field schema)."""
    return _get_root_schema()["properties"]["edition"]["properties"]


def get_original_fields() -> Dict[str, Dict[str, Any]]:
    """Get original work field definitions (name -> field schema)."""
    return _get_root_schema()["properties"]["original"]["properties"]


def get_confidence_field() -> Dict[str, Any]:
    """Get confidence field definition."""
    return _get_root_schema()["properties"]["confidence"]


def get_field_type(field_def: Dict[str, Any]) -> str:
    """
    Extract a normalised type string from a JSON Schema field definition.

    Returns the same vocabulary as v1 so callers don't need to change:
      'string' | 'integer' | 'number' | 'date' | 'array[string]' | 'array[integer]'
    """
    json_type = field_def.get("type", "string")

    if json_type == "array":
        items_type = field_def.get("items", {}).get("type", "string")
        return f"array[{items_type}]"

    # Fields that carry an ISO-date pattern are surfaced as 'date' for callers
    # that relied on that v1 type name.
    if json_type == "string" and "pattern" in field_def:
        pattern = field_def["pattern"]
        if r"\d{4}-\d{2}-\d{2}" in pattern:
            return "date"

    return json_type


def is_field_optional(field_def: Dict[str, Any], field_name: str, parent_key: str = "edition") -> bool:
    """
    Check if a field is optional.

    In v2 the optionality is encoded in the parent object's 'required' array,
    not on the field itself.  Pass the parent section ('edition' or 'original')
    and the field name to get the correct answer.
    """
    root = _get_root_schema()
    parent = root["properties"].get(parent_key, {})
    required_fields: List[str] = parent.get("required", [])
    return field_name not in required_fields


def get_prompt_label(field_def: Dict[str, Any]) -> str:
    """
    Get human-readable label for prompts.

    v2 has no dedicated prompt_label; we fall back to the 'description' field
    (first sentence, capitalised) so callers keep working without changes.
    """
    description = field_def.get("description", "")
    if not description:
        return ""
    # Use only the first sentence as a short label
    first_sentence = description.split(".")[0].strip()
    return first_sentence


def get_ai_hint(field_def: Dict[str, Any]) -> str:
    """Get AI hint for field.  In v2 this is the 'description' property."""
    return field_def.get("description", "")


def parse_type_string(type_str: str) -> Tuple[type, bool]:
    """
    Parse a normalised type string (as returned by get_field_type) into a
    Python type and an is_array flag.

    Accepts: 'string', 'integer', 'number', 'date', 'array[string]', 'array[integer]'
    """
    is_array = False

    if type_str.startswith("array[") and type_str.endswith("]"):
        is_array = True
        type_str = type_str[6:-1]

    type_map: Dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "date": str,  # ISO date string
    }

    python_type = type_map.get(type_str, str)
    return python_type, is_array


def validate_field_value(value: Any, field_def: Dict[str, Any]) -> bool:
    """Validate value against field definition."""
    type_str = get_field_type(field_def)
    python_type, is_array = parse_type_string(type_str)

    if is_array:
        if not isinstance(value, list):
            return False
        return all(isinstance(item, python_type) for item in value)

    if type_str == "date":
        if not isinstance(value, str):
            return False
        try:
            datetime.fromisoformat(value)
            return True
        except ValueError:
            return False

    if type_str == "number":
        return isinstance(value, (int, float))

    return isinstance(value, python_type)


def get_rules() -> List[str]:
    """
    Return semantic rules about the schema.

    v2 has no 'rules' array; we reconstruct the same logical rules from the
    schema itself so that any prompt-building code that calls this keeps working.
    """
    return [
        "All fields that are not in the 'required' list are optional.",
        "edition describes the concrete file/edition being catalogued.",
        "original describes the original work (possibly in a different language).",
        "If edition.language differs from original.language, this is a translation.",
        "Unknown fields must be ignored (additionalProperties is false).",
        "Use empty string for absent string fields, 0 for absent integer fields.",
    ]