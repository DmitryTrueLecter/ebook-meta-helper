"""
Schema loader and utilities for working with book_metadata schema.
Provides centralized access to field definitions, types, and AI hints.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


_SCHEMA_CACHE: Optional[Dict[str, Any]] = None


def _load_schema() -> Dict[str, Any]:
    """Load schema from book_metadata.v1.json"""
    global _SCHEMA_CACHE

    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE

    schema_path = Path(__file__).parent / "book_metadata.v1.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        _SCHEMA_CACHE = json.load(f)

    return _SCHEMA_CACHE


def get_schema() -> Dict[str, Any]:
    """Get full schema"""
    return _load_schema()


def get_edition_fields() -> Dict[str, Dict[str, Any]]:
    """Get edition field definitions"""
    schema = _load_schema()
    return schema["fields"]["edition"]


def get_original_fields() -> Dict[str, Dict[str, Any]]:
    """Get original work field definitions"""
    schema = _load_schema()
    return schema["fields"]["original"]


def get_confidence_field() -> Dict[str, Any]:
    """Get confidence field definition"""
    schema = _load_schema()
    return schema["fields"]["confidence"]


def get_field_type(field_def: Dict[str, Any]) -> str:
    """Extract type from field definition"""
    return field_def.get("type", "string")


def is_field_optional(field_def: Dict[str, Any]) -> bool:
    """Check if field is optional"""
    return field_def.get("optional", True)


def get_prompt_label(field_def: Dict[str, Any]) -> str:
    """Get human-readable label for prompts"""
    return field_def.get("prompt_label", "")


def get_ai_hint(field_def: Dict[str, Any]) -> str:
    """Get AI hint for field"""
    return field_def.get("ai_hint", "")


def parse_type_string(type_str: str) -> tuple[type, bool]:
    """
    Parse type string like 'string', 'integer', 'array[string]', 'date'
    Returns (python_type, is_array)
    """
    is_array = False

    if type_str.startswith("array[") and type_str.endswith("]"):
        is_array = True
        inner_type = type_str[6:-1]
        type_str = inner_type

    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "date": str,  # ISO date string
    }

    python_type = type_map.get(type_str, str)
    return python_type, is_array


def validate_field_value(value: Any, field_def: Dict[str, Any]) -> bool:
    """Validate value against field definition"""
    type_str = get_field_type(field_def)
    python_type, is_array = parse_type_string(type_str)

    if is_array:
        if not isinstance(value, list):
            return False
        return all(isinstance(item, python_type) for item in value)

    if type_str == "date":
        # Special validation for ISO date
        if not isinstance(value, str):
            return False
        try:
            datetime.fromisoformat(value)
            return True
        except ValueError:
            return False

    # Special case for number type - accept both int and float
    if type_str == "number":
        return isinstance(value, (int, float))

    return isinstance(value, python_type)


def get_rules() -> List[str]:
    """Get schema rules for AI"""
    schema = _load_schema()
    return schema.get("rules", [])
