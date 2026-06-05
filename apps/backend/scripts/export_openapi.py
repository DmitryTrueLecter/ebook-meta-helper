"""Export the FastAPI OpenAPI schema to the committed contract artifact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.api.main import app

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contract" / "openapi.json"


def render_openapi(schema: dict[str, Any]) -> str:
    """Serialize an OpenAPI schema deterministically — stable key order, trailing newline."""
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_contract(destination: Path) -> None:
    """Render the assembled app's OpenAPI schema and write it to ``destination``."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_openapi(app.openapi()), encoding="utf-8")


if __name__ == "__main__":
    write_contract(CONTRACT_PATH)
    print(f"Wrote {CONTRACT_PATH}")
