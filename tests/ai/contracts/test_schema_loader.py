"""Tests for schema_loader functionality"""

from ai.contracts.schema_loader import (
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
    """Test that schema loads successfully"""
    schema = get_schema()

    assert schema is not None
    assert "version" in schema
    assert "fields" in schema
    assert schema["version"] == "1.0"


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
    """Test getting confidence field definition"""
    field = get_confidence_field()

    assert isinstance(field, dict)
    assert "type" in field
    assert field["type"] == "number"
    assert "range" in field


def test_get_field_type():
    """Test extracting field type"""
    field_def = {"type": "string", "optional": True}
    assert get_field_type(field_def) == "string"

    field_def = {"type": "integer"}
    assert get_field_type(field_def) == "integer"


def test_is_field_optional():
    """Test checking if field is optional"""
    field_def = {"type": "string", "optional": True}
    assert is_field_optional(field_def) is True

    field_def = {"type": "string", "optional": False}
    assert is_field_optional(field_def) is False

    # Default is True
    field_def = {"type": "string"}
    assert is_field_optional(field_def) is True


def test_get_prompt_label():
    """Test getting prompt label"""
    field_def = {"type": "string", "prompt_label": "Title"}
    assert get_prompt_label(field_def) == "Title"

    field_def = {"type": "string"}
    assert get_prompt_label(field_def) == ""


def test_get_ai_hint():
    """Test getting AI hint"""
    field_def = {"type": "string", "ai_hint": "The book title"}
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
    """Test that all edition fields have required properties"""
    fields = get_edition_fields()

    for field_name, field_def in fields.items():
        assert "type" in field_def, f"{field_name} missing 'type'"
        assert "optional" in field_def, f"{field_name} missing 'optional'"
        assert "prompt_label" in field_def, f"{field_name} missing 'prompt_label'"
        assert "ai_hint" in field_def, f"{field_name} missing 'ai_hint'"


def test_all_original_fields_have_required_properties():
    """Test that all original fields have required properties"""
    fields = get_original_fields()

    for field_name, field_def in fields.items():
        assert "type" in field_def, f"{field_name} missing 'type'"
        assert "optional" in field_def, f"{field_name} missing 'optional'"
        assert "prompt_label" in field_def, f"{field_name} missing 'prompt_label'"
        assert "ai_hint" in field_def, f"{field_name} missing 'ai_hint'"
