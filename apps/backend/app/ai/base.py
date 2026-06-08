from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.models.book import BookRecord


@dataclass(frozen=True)
class AICallRecord:
    """One AI provider call captured for observability — crosses the provider boundary."""

    system_prompt: str
    user_prompt: str
    raw_response: str
    model: str
    response_format_ref: str
    duration_ms: int
    tier: str  # cheap | expensive
    sequence: int  # 0-based
    effort: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cost_usd: Optional[Decimal] = None
    confidence: Optional[float] = None
    parse_errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EnrichOutcome:
    """Result Object of a provider enrich: the canonical record plus every call made to produce it."""

    record: BookRecord
    calls: list[AICallRecord]
    canonical_sequence: int


@dataclass(frozen=True)
class AIConfigSnapshot:
    """Runtime AI configuration passed into enrich() — read from the active config, never from os.environ."""

    system_prompt: str
    cheap_model: str
    expensive_model: str
    escalation_threshold: float
    response_format_ref: str
    provider: str
    effort: Optional[str] = None


class AIProvider(ABC):
    name: str  # "openai", "dummy", etc.

    @abstractmethod
    def enrich(
        self,
        record: BookRecord,
        config: AIConfigSnapshot,
        directory_hint: Optional[dict] = None,
    ) -> EnrichOutcome:
        """Return an EnrichOutcome with a NEW BookRecord; must not mutate input."""
        raise NotImplementedError

    @abstractmethod
    def summarize_directory(
        self, files: list[BookRecord], config: AIConfigSnapshot
    ) -> dict:
        """Collapse a directory of files into the SUMMARY_KEYS-shaped hint dict."""
        raise NotImplementedError
