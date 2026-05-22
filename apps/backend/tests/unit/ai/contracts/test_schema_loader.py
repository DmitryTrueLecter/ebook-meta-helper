"""Tests for schema_loader functionality"""

from app.ai.contracts import schema_loader
from app.ai.contracts.schema_loader import (
    get_schema,
    get_edition_fields,
    get_original_fields,
    get_confidence_field,
    get_field_type,
    is_field_optional,
    get_prompt_label,
    get_ai_hint,
    parse_type_string,
    validate_field_value,
    get_rules,
)


def test_get_schema():
    """Schema loads in v2 OpenAI json_schema format with edition/original/confidence sections."""
    schema = get_schema()

    assert schema is not None
    assert "format" in schema
    assert schema["format"]["type"] == "json_schema"
    assert schema["format"]["name"] == "book_edition_info"
    assert "schema" in schema["format"]
    root = schema["format"]["schema"]
    assert "properties" in root
    assert {"edition", "original", "confidence"} <= set(root["properties"].keys())


def test_get_edition_fields():
    """Test getting edition field definitions"""
    fields = get_edition_fields()

    assert isinstance(fields, dict)
    assert "title" in fields
    assert "authors" in fields
    assert "series" in fields
    assert "language" in fields
    assert "publisher" in fields
    assert "isbn10" in fields
    assert "isbn13" in fields
    assert "asin" in fields


def test_get_original_fields():
    """Test getting original work field definitions"""
    fields = get_original_fields()

    assert isinstance(fields, dict)
    assert "title" in fields
    assert "authors" in fields
    assert "language" in fields
    assert "year" in fields


def test_get_confidence_field():
    """Confidence field is a v2 number with minimum/maximum bounds."""
    field = get_confidence_field()

    assert isinstance(field, dict)
    assert "type" in field
    assert field["type"] == "number"
    assert field["minimum"] == 0
    assert field["maximum"] == 1


def test_get_field_type():
    """Test extracting field type"""
    field_def = {"type": "string", "optional": True}
    assert get_field_type(field_def) == "string"

    field_def = {"type": "integer"}
    assert get_field_type(field_def) == "integer"


def test_is_field_optional(monkeypatch):
    """Optionality is driven by the parent object's v2 'required' array, not a per-field key."""
    fake_root = {
        "properties": {
            "edition": {
                "properties": {
                    "title": {"type": "string"},
                    "subtitle": {"type": "string"},
                },
                "required": ["title"],
            },
            "original": {
                "properties": {
                    "title": {"type": "string"},
                },
                "required": ["title"],
            },
        }
    }
    monkeypatch.setattr(schema_loader, "_get_root_schema", lambda: fake_root)

    # Listed in parent's required -> not optional.
    assert is_field_optional({"type": "string"}, "title", "edition") is False
    # Absent from parent's required -> optional.
    assert is_field_optional({"type": "string"}, "subtitle", "edition") is True
    # Unknown parent section -> required list missing -> treated as optional.
    assert is_field_optional({"type": "string"}, "title", "nonexistent") is True
    # parent_key defaults to "edition".
    assert is_field_optional({"type": "string"}, "title") is False
    assert is_field_optional({"type": "string"}, "subtitle") is True


def test_get_prompt_label():
    """v2 derives the prompt label from the first sentence of 'description'."""
    # Single-sentence description: used as-is (no trailing period).
    field_def = {"type": "string", "description": "Title of the book"}
    assert get_prompt_label(field_def) == "Title of the book"

    # Multi-sentence description: only the first sentence.
    field_def = {"type": "string", "description": "Title of the book. Long form allowed."}
    assert get_prompt_label(field_def) == "Title of the book"

    # No description -> empty.
    field_def = {"type": "string"}
    assert get_prompt_label(field_def) == ""


def test_get_ai_hint():
    """v2 surfaces the field 'description' as the AI hint verbatim."""
    field_def = {"type": "string", "description": "The book title"}
    assert get_ai_hint(field_def) == "The book title"

    field_def = {"type": "string"}
    assert get_ai_hint(field_def) == ""


def test_parse_type_string_basic():
    """Test parsing basic type strings"""
    python_type, is_array = parse_type_string("string")
    assert python_type is str
    assert is_array is False

    python_type, is_array = parse_type_string("integer")
    assert python_type is int
    assert is_array is False

    python_type, is_array = parse_type_string("number")
    assert python_type is float
    assert is_array is False

    python_type, is_array = parse_type_string("date")
    assert python_type is str
    assert is_array is False


def test_parse_type_string_array():
    """Test parsing array type strings"""
    python_type, is_array = parse_type_string("array[string]")
    assert python_type is str
    assert is_array is True


def test_validate_field_value_string():
    """Test validating string values"""
    field_def = {"type": "string"}

    assert validate_field_value("test", field_def) is True
    assert validate_field_value(123, field_def) is False


def test_validate_field_value_integer():
    """Test validating integer values"""
    field_def = {"type": "integer"}

    assert validate_field_value(123, field_def) is True
    assert validate_field_value("123", field_def) is False


def test_validate_field_value_number():
    """Test validating number values"""
    field_def = {"type": "number"}

    assert validate_field_value(123.45, field_def) is True
    assert validate_field_value(123, field_def) is True  # int is also valid for number
    assert validate_field_value("123", field_def) is False  # string is not valid


def test_validate_field_value_array():
    """Test validating array values"""
    field_def = {"type": "array[string]"}

    assert validate_field_value(["a", "b"], field_def) is True
    assert validate_field_value([], field_def) is True
    assert validate_field_value(["a", 1], field_def) is False  # Mixed types
    assert validate_field_value("not-array", field_def) is False


def test_validate_field_value_date():
    """Test validating date values"""
    field_def = {"type": "date"}

    assert validate_field_value("2020-05-15", field_def) is True
    assert validate_field_value("2020-13-45", field_def) is False  # Invalid date
    assert validate_field_value("not-a-date", field_def) is False
    assert validate_field_value(123, field_def) is False


def test_get_rules():
    """Test getting schema rules"""
    rules = get_rules()

    assert isinstance(rules, list)
    assert len(rules) > 0
    assert any("optional" in rule.lower() for rule in rules)


def test_schema_caching():
    """Test that schema is cached after first load"""
    schema1 = get_schema()
    schema2 = get_schema()

    # Should return the same cached object
    assert schema1 is schema2


def test_all_edition_fields_have_required_properties():
    """Every v2 edition field declares 'type' and 'description'."""
    fields = get_edition_fields()

    for field_name, field_def in fields.items():
        assert "type" in field_def, f"{field_name} missing 'type'"
        assert "description" in field_def, f"{field_name} missing 'description'"


def test_all_original_fields_have_required_properties():
    """Every v2 original-work field declares 'type' and 'description'."""
    fields = get_original_fields()

    for field_name, field_def in fields.items():
        assert "type" in field_def, f"{field_name} missing 'type'"
        assert "description" in field_def, f"{field_name} missing 'description'"
