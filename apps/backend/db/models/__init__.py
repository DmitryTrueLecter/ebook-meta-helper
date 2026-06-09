"""SQLAlchemy table models."""

from db.base import Base
from db.models.ai_call import AICall, AICallOrigin, AICallTier
from db.models.ai_config_version import AIConfigVersion
from db.models.directory import Directory, DirectoryStatus
from db.models.directory_hint import DirectoryHint
from db.models.enrichment_run import (
    EnrichmentRun,
    EnrichmentStatus,
    EnrichmentTrigger,
)
from db.models.file_record import FileRecord, FileStatus
from db.models.metadata import Metadata, MetadataSource
from db.models.processing_log import (
    ProcessingLog,
    ProcessingLogLevel,
    ProcessingStep,
)
from db.models.scan_job import ScanJob, ScanJobStatus

__all__ = [
    "Base",
    "AICall",
    "AICallOrigin",
    "AICallTier",
    "AIConfigVersion",
    "Directory",
    "DirectoryStatus",
    "DirectoryHint",
    "EnrichmentRun",
    "EnrichmentStatus",
    "EnrichmentTrigger",
    "FileRecord",
    "FileStatus",
    "Metadata",
    "MetadataSource",
    "ProcessingLog",
    "ProcessingLogLevel",
    "ProcessingStep",
    "ScanJob",
    "ScanJobStatus",
]
