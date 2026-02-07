import json
from datetime import datetime
from typing import Any, Dict, Tuple, List


_ALLOWED_EDITION_FIELDS = {
    "title": str,
    "subtitle": str,
    "authors": list,
    "series": str,
    "series_index": int,
    "series_total": int,
    "language": str,
    "publisher": str,
    "isbn10": str,
    "isbn13": str,
    "asin": str,
    "published": str,  # ISO date string
    "year": int,
}

_ALLOWED_ORIGINAL_FIELDS = {
    "title": str,
    "authors": list,
    "language": str,
    "year": int,
}


def parse_book_metadata_v1(raw: Any) -> Tuple[Dict[str, Any], List[str]]:
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

    # --- Edition ---
    edition = data.get("edition")
    if edition is not None:
        if not isinstance(edition, dict):
            errors.append("edition must be an object")
        else:
            parsed_edition = {}
            for field, field_type in _ALLOWED_EDITION_FIELDS.items():
                if field in edition:
                    value = edition[field]
                    if _validate_type(value, field_type, field):
                        # --- special handling for date ---
                        if field == "published" and isinstance(value, str):
                            try:
                                parsed_edition[field] = datetime.fromisoformat(value).date()
                            except ValueError:
                                errors.append(f"edition.published invalid ISO date: {value}")
                        else:
                            parsed_edition[field] = value
                    else:
                        errors.append(f"edition.{field} has invalid type")
            if parsed_edition:
                parsed["edition"] = parsed_edition

    # --- Original ---
    original = data.get("original")
    if original is not None:
        if not isinstance(original, dict):
            errors.append("original must be an object")
        else:
            parsed_original = {}
            for field, field_type in _ALLOWED_ORIGINAL_FIELDS.items():
                if field in original:
                    value = original[field]
                    if _validate_type(value, field_type, field):
                        parsed_original[field] = value
                    else:
                        errors.append(f"original.{field} has invalid type")
            if parsed_original:
                parsed["original"] = parsed_original

    # --- Confidence ---
    confidence = data.get("confidence")
    if confidence is not None:
        if isinstance(confidence, (int, float)):
            if 0.0 <= float(confidence) <= 1.0:
                parsed["confidence"] = float(confidence)
            else:
                errors.append("confidence out of range 0..1")
        else:
            errors.append("confidence must be a number")

    return parsed, errors


def _validate_type(value: Any, expected: type, field_name: str) -> bool:
    if expected is list:
        if not isinstance(value, list):
            return False
        return all(isinstance(v, str) for v in value)
    return isinstance(value, expected)
