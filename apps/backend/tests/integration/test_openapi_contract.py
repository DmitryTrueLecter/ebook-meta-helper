"""Integration tests for the committed OpenAPI contract — against the real assembled app."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from fastapi.testclient import TestClient
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from decimal import Decimal

from app.api.deps import get_db
from app.api.main import app
from db.models.ai_call import AICall, AICallOrigin, AICallTier
from db.models.ai_config_version import AIConfigVersion
from db.models.directory import Directory
from db.models.file_record import FileRecord, FileStatus
from scripts.export_openapi import CONTRACT_PATH, render_openapi, write_contract


def _validate_against_contract(payload, schema_ref: str) -> None:
    """Validate a route payload against a $ref in the committed contract — fails on ORM leakage."""
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_uri = "urn:openapi-contract"
    registry = Registry().with_resource(
        contract_uri,
        Resource.from_contents(contract, default_specification=DRAFT202012),
    )
    wrapper = {"$ref": f"{contract_uri}{schema_ref}"}
    jsonschema.Draft202012Validator(wrapper, registry=registry).validate(payload)


def _component_ref(name: str) -> str:
    return f"#/components/schemas/{name}"


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


def _seed_file(session) -> int:
    directory = Directory(path="/library/ai", name="ai", parent_id=None, depth=0)
    session.add(directory)
    session.flush()
    record = FileRecord(
        directory_id=directory.id,
        filename="book.epub",
        extension="epub",
        format="EPUB",
        status=FileStatus.enriched,
    )
    session.add(record)
    session.flush()
    return record.id


def _seed_ai_call(session, file_id: int) -> int:
    call = AICall(
        file_id=file_id,
        enrichment_run_id=None,
        config_version_id=None,
        origin=AICallOrigin.pipeline,
        sequence=1,
        tier=AICallTier.cheap,
        is_canonical=True,
        model="gpt-4o-mini",
        effort=None,
        response_format_ref="book.v1",
        system_prompt="You are a librarian.",
        user_prompt="Extract metadata.",
        raw_response='{"title": "Foundation"}',
        prompt_tokens=120,
        completion_tokens=40,
        cost_usd=Decimal("0.001234"),
        duration_ms=850,
        confidence=Decimal("0.910"),
        parse_errors=None,
    )
    session.add(call)
    session.flush()
    return call.id


def _seed_ai_config_version(session) -> int:
    version = AIConfigVersion(
        version=1,
        label="initial",
        system_prompt="You are a librarian.",
        cheap_model="gpt-4o-mini",
        expensive_model="gpt-4o",
        effort="medium",
        escalation_threshold=Decimal("0.700"),
        provider="openai",
        response_format_ref="book.v1",
        is_active=True,
        created_by="seed",
    )
    session.add(version)
    session.flush()
    return version.id


def test_ai_call_list_payload_satisfies_committed_schema(session) -> None:
    """Round-trip: GET /api/files/{id}/ai-calls validates against the committed AICallSummary schema."""
    file_id = _seed_file(session)
    _seed_ai_call(session, file_id)
    session.commit()

    app.dependency_overrides[get_db] = lambda: session
    try:
        response = TestClient(app).get(f"/api/files/{file_id}/ai-calls")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    for item in payload:
        _validate_against_contract(item, _component_ref("AICallSummary"))
    assert "system_prompt" not in payload[0]
    assert "raw_response" not in payload[0]


def test_ai_call_detail_payload_satisfies_committed_schema(session) -> None:
    """Round-trip: GET /api/ai-calls/{id} validates against the committed AICallDetail schema."""
    file_id = _seed_file(session)
    call_id = _seed_ai_call(session, file_id)
    session.commit()

    app.dependency_overrides[get_db] = lambda: session
    try:
        response = TestClient(app).get(f"/api/ai-calls/{call_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    _validate_against_contract(payload, _component_ref("AICallDetail"))
    assert payload["system_prompt"] == "You are a librarian."
    assert payload["raw_response"] == '{"title": "Foundation"}'
    assert payload["origin"] == "pipeline"


def test_ai_config_active_payload_satisfies_committed_schema(session) -> None:
    """Round-trip: GET /api/ai-config/active validates against the committed AIConfigVersionView schema."""
    _seed_ai_config_version(session)
    session.commit()

    app.dependency_overrides[get_db] = lambda: session
    try:
        response = TestClient(app).get("/api/ai-config/active")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    _validate_against_contract(payload, _component_ref("AIConfigVersionView"))
    assert payload["is_active"] is True
    assert payload["escalation_threshold"] == 0.7


def test_ai_config_versions_payload_satisfies_committed_schema(session) -> None:
    """Round-trip: GET /api/ai-config/versions validates against the committed AIConfigVersionView schema."""
    _seed_ai_config_version(session)
    session.commit()

    app.dependency_overrides[get_db] = lambda: session
    try:
        response = TestClient(app).get("/api/ai-config/versions")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    for item in payload:
        _validate_against_contract(item, _component_ref("AIConfigVersionView"))
