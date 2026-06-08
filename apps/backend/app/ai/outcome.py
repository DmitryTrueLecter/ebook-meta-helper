"""Provider-boundary DTOs for enrich(); coordinated with (and superseded by) the DTO-contract task."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, List, Optional

from app.models.book import BookRecord


@dataclass(frozen=True)
class AICallRecord:
    """One model invocation in an escalation chain. `sequence` is 0-based, chain order."""

    sequence: int
    tier: str
    model: str
    response_format_ref: str
    system_prompt: str
    user_prompt: str
    raw_response: str
    duration_ms: int
    effort: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cost_usd: Optional[Decimal] = None
    confidence: Optional[Decimal] = None
    parse_errors: Optional[Any] = None


@dataclass(frozen=True)
class EnrichOutcome:
    """Result of one enrich(): the chosen record plus every call made to produce it."""

    record: BookRecord
    calls: List[AICallRecord] = field(default_factory=list)
    canonical_sequence: int = 0
