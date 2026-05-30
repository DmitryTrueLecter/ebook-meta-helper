"""Unit tests for app.api.schemas."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.api.schemas import (
    DirectoryDetail,
    DirectoryNode,
    EnrichmentTriggerResponse,
    FileDetail,
    FileListItem,
    MetadataSnapshot,
    PaginatedFiles,
    ProcessingLogEntry,
    ScanJobStatus,
)


class TestDirectoryNode:
    def test_minimal_valid_payload_defaults_children_to_empty_list(self):
        node = DirectoryNode(
            id=1, name="Sci-Fi", path="/library/sci-fi", depth=1,
            file_count=10, pending_count=3, enriched_count=5, accepted_count=2,
        )
        assert node.children == []

    def test_nested_children_are_directory_nodes(self):
        node = DirectoryNode(
            id=1, name="root", path="/library", depth=0,
            file_count=20, pending_count=0, enriched_count=10, accepted_count=10,
            children=[
                {
                    "id": 2, "name": "child", "path": "/library/child", "depth": 1,
                    "file_count": 5, "pending_count": 1, "enriched_count": 2, "accepted_count": 2,
                    "children": [
                        {
                            "id": 3, "name": "grandchild", "path": "/library/child/g",
                            "depth": 2, "file_count": 0, "pending_count": 0,
                            "enriched_count": 0, "accepted_count": 0,
                        },
                    ],
                },
            ],
        )
        assert len(node.children) == 1
        assert isinstance(node.children[0], DirectoryNode)
        assert isinstance(node.children[0].children[0], DirectoryNode)
        assert node.children[0].children[0].name == "grandchild"

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError) as exc:
            DirectoryNode(
                id=1, name="x", path="/x", depth=0,
                file_count=0, pending_count=0, enriched_count=0,
                # accepted_count omitted
            )
        assert "accepted_count" in str(exc.value)

    def test_from_attributes_projects_orm_like_object(self):
        orm = SimpleNamespace(
            id=42, name="Library", path="/library", depth=0,
            file_count=100, pending_count=50, enriched_count=30, accepted_count=20,
            children=[],
        )
        node = DirectoryNode.model_validate(orm)
        assert node.id == 42
        assert node.name == "Library"


class TestFileListItem:
    def test_valid_payload(self):
        item = FileListItem(
            id=1, filename="book.epub", extension="epub", format="EPUB",
            status="pending", has_ai_suggestion=False, sort_order=1.5,
        )
        assert item.status == "pending"
        assert item.sort_order == 1.5

    def test_nullable_format_and_sort_order(self):
        item = FileListItem(
            id=1, filename="book.fb2", extension="fb2", format=None,
            status="enriched", has_ai_suggestion=True, sort_order=None,
        )
        assert item.format is None
        assert item.sort_order is None

    def test_extension_nullable(self):
        item = FileListItem(
            id=1, filename="README", extension=None, format=None,
            status="pending", has_ai_suggestion=False, sort_order=None,
        )
        assert item.extension is None


class TestDirectoryDetail:
    def test_minimal_valid_payload_defaults_files_to_empty(self):
        detail = DirectoryDetail(
            id=1, name="lib", path="/lib", depth=0,
            file_count=0, pending_count=0, enriched_count=0, accepted_count=0,
        )
        assert detail.files == []

    def test_nested_files_are_file_list_items(self):
        detail = DirectoryDetail(
            id=1, name="lib", path="/lib", depth=0,
            file_count=1, pending_count=1, enriched_count=0, accepted_count=0,
            files=[{
                "id": 10, "filename": "a.epub", "extension": "epub",
                "format": "EPUB", "status": "pending",
                "has_ai_suggestion": False, "sort_order": None,
            }],
        )
        assert len(detail.files) == 1
        assert isinstance(detail.files[0], FileListItem)
        assert detail.files[0].filename == "a.epub"


class TestMetadataSnapshot:
    def _payload(self, **overrides):
        base = {
            "id": 7,
            "source": "ai",
            "is_current": True,
            "title": "Foundation",
            "subtitle": None,
            "language": "en",
            "series": "Foundation",
            "series_index": 1,
            "isbn13": "9780553293357",
            "confidence": 0.92,
            "data": {"authors": ["Isaac Asimov"], "tags": ["sci-fi"]},
            "created_at": datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc),
        }
        base.update(overrides)
        return base

    def test_valid_payload(self):
        snap = MetadataSnapshot(**self._payload())
        assert snap.title == "Foundation"
        assert snap.data["authors"] == ["Isaac Asimov"]

    def test_nullable_scalars(self):
        snap = MetadataSnapshot(**self._payload(
            title=None, subtitle=None, language=None, series=None,
            series_index=None, isbn13=None, confidence=None,
        ))
        assert snap.title is None
        assert snap.confidence is None

    def test_data_must_be_dict(self):
        with pytest.raises(ValidationError):
            MetadataSnapshot(**self._payload(data=["not", "a", "dict"]))

    def test_arbitrary_keys_allowed_inside_data(self):
        payload = self._payload(data={
            "authors": ["A"],
            "tags": ["t"],
            "description": "desc",
            "original": {"title": "Original", "language": "ru"},
        })
        snap = MetadataSnapshot(**payload)
        assert snap.data["original"]["language"] == "ru"


class TestProcessingLogEntry:
    def test_valid_payload(self):
        entry = ProcessingLogEntry(
            step="ai_enrich", level="info", message="enriched",
            duration_ms=1234,
            created_at=datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc),
        )
        assert entry.duration_ms == 1234

    def test_duration_optional(self):
        entry = ProcessingLogEntry(
            step="read", level="error", message="boom",
            duration_ms=None,
            created_at=datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc),
        )
        assert entry.duration_ms is None


class TestScanJobStatus:
    def test_valid_payload(self):
        status = ScanJobStatus(
            id=5, status="running", files_discovered=100,
            files_processed=42, current_filename="book.epub",
        )
        assert status.files_processed == 42

    def test_current_filename_optional(self):
        status = ScanJobStatus(
            id=5, status="finished", files_discovered=100,
            files_processed=100, current_filename=None,
        )
        assert status.current_filename is None


class TestPaginatedFiles:
    def _item(self, **overrides):
        base = {
            "id": 1, "filename": "a.epub", "extension": "epub", "format": "EPUB",
            "status": "pending", "has_ai_suggestion": False, "sort_order": None,
        }
        base.update(overrides)
        return base

    def test_valid_payload(self):
        page = PaginatedFiles(items=[self._item()], total=42, page=1, page_size=50)
        assert page.total == 42
        assert page.items[0].filename == "a.epub"

    def test_empty_items_allowed(self):
        page = PaginatedFiles(items=[], total=0, page=1, page_size=50)
        assert page.items == []


class TestFileDetail:
    def _payload(self, **overrides):
        base = {
            "id": 7,
            "directory_id": 3,
            "filename": "book.epub",
            "extension": "epub",
            "format": "EPUB",
            "status": "enriched",
            "sort_order": 1.0,
            "error_message": None,
            "file_metadata": None,
            "ai_metadata": None,
        }
        base.update(overrides)
        return base

    def test_minimal_payload_with_no_metadata(self):
        detail = FileDetail(**self._payload())
        assert detail.file_metadata is None
        assert detail.ai_metadata is None

    def test_nested_metadata_snapshots(self):
        snapshot = {
            "id": 10, "source": "ai", "is_current": True,
            "title": "T", "subtitle": None, "language": "en", "series": None,
            "series_index": None, "isbn13": None, "confidence": 0.9,
            "data": {}, "created_at": datetime(2026, 5, 1, tzinfo=timezone.utc),
        }
        detail = FileDetail(**self._payload(ai_metadata=snapshot))
        assert detail.ai_metadata is not None
        assert detail.ai_metadata.title == "T"


class TestEnrichmentTriggerResponse:
    def test_valid_payload(self):
        resp = EnrichmentTriggerResponse(enrichment_run_id=99, file_id=5, status="ai_queued")
        assert resp.enrichment_run_id == 99
        assert resp.status == "ai_queued"
