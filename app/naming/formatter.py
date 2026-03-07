from datetime import date
from typing import Any, Optional


def format_value(value: Any, fmt: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, date):
        if fmt:
            py_fmt = (
                fmt.replace("yyyy", "%Y")
                   .replace("MM", "%m")
                   .replace("dd", "%d")
            )
            return value.strftime(py_fmt)
        return value.isoformat()

    return str(value)
