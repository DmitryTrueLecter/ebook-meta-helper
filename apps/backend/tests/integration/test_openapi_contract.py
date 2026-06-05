"""Integration tests for the committed OpenAPI contract — against the real assembled app."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from fastapi.testclient import TestClient
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from app.api.deps import get_db
from app.api.main import app
from db.models.directory import Directory
from db.models.file_record import FileRecord, FileStatus
from scripts.export_openapi import CONTRACT_PATH, render_openapi, write_contract


def test_committed_contract_matches_exporter_output(tmp_path: Path) -> None:
    """Re-export against the real app and assert byte-equality with the committed file."""
    regenerated = tmp_path / "openapi.json"
    write_contract(regenerated)

    expected = regenerated.read_text(encoding="utf-8")
    committed = CONTRACT_PATH.read_text(encoding="utf-8")

    assert committed == expected, (
        "apps/backend/contract/openapi.json is stale — "
        "re-run `python scripts/export_openapi.py` and commit the result."
    )


def test_render_is_deterministic_and_newline_terminated() -> None:
    """sort_keys + fixed indent + trailing newline — the load-bearing serialization invariants."""
    rendered = render_openapi(app.openapi())
    assert rendered.endswith("\n")
    assert render_openapi(app.openapi()) == rendered
    parsed = json.loads(rendered)
    assert rendered == json.dumps(parsed, indent=2, sort_keys=True) + "\n"


def _seed_directory_with_nullable_extension_file(session) -> int:
    directory = Directory(path="/library/sci-fi", name="sci-fi", parent_id=None, depth=0)
    session.add(directory)
    session.flush()
    session.add(
        FileRecord(
            directory_id=directory.id,
            filename="README",
            extension=None,
            format=None,
            status=FileStatus.pending,
        )
    )
    session.commit()
    return directory.id


def test_directory_detail_payload_satisfies_committed_schema(session) -> None:
    """Round-trip: a real route's payload validates against the committed schema (extension nullable)."""
    directory_id = _seed_directory_with_nullable_extension_file(session)
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    app.dependency_overrides[get_db] = lambda: session
    try:
        client = TestClient(app)
        response = client.get(f"/api/directories/{directory_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()

    detail_ref = contract["paths"]["/api/directories/{directory_id}"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]["$ref"]

    contract_uri = "urn:openapi-contract"
    registry = Registry().with_resource(
        contract_uri,
        Resource.from_contents(contract, default_specification=DRAFT202012),
    )
    wrapper = {"$ref": f"{contract_uri}{detail_ref}"}
    jsonschema.Draft202012Validator(wrapper, registry=registry).validate(payload)

    file_item = payload["files"][0]
    assert file_item["extension"] is None
    assert file_item["status"] == FileStatus.pending.value
