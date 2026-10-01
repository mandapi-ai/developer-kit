from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


PRICE_COLUMNS = [
    "record_id",
    "model_id",
    "canonical_model_id",
    "model_name",
    "model_family",
    "model_provider",
    "platform",
    "platform_type",
    "source_type",
    "currency",
    "input_per_1m",
    "output_per_1m",
    "cache_read_per_1m",
    "cache_write_per_1m",
    "context_tier",
    "context_limit_tokens",
    "pricing_variant",
    "price_scope",
    "market_scope",
    "brazil_relevance",
    "openai_compatible",
    "verification_status",
    "last_checked",
    "source_url",
    "notes",
]


@dataclass(slots=True)
class SourceSpec:
    id: str
    platform: str
    enabled: bool
    adapter: str
    pricing_url: str
    platform_type: str
    source_type: str
    default_currency: str
    market_scope: str
    brazil_relevance: str
    openai_compatible: bool
    unit: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Evidence:
    source_id: str
    platform: str
    url: str
    fetched_at: str
    status_code: int | None
    sha256: str | None
    adapter: str
    ok: bool
    content_type: str | None = None
    error: str | None = None
    parser_status: str = "not_attempted"
    record_count: int = 0


@dataclass(slots=True)
class PriceRecord:
    record_id: str
    model_id: str
    canonical_model_id: str
    model_name: str
    model_family: str
    model_provider: str
    platform: str
    platform_type: str
    source_type: str
    currency: str
    input_per_1m: Decimal | None = None
    output_per_1m: Decimal | None = None
    cache_read_per_1m: Decimal | None = None
    cache_write_per_1m: Decimal | None = None
    context_tier: str = ""
    context_limit_tokens: int | None = None
    pricing_variant: str = "standard"
    price_scope: str = "retail_price"
    market_scope: str = "Global"
    brazil_relevance: str = "global_reference"
    openai_compatible: bool = False
    verification_status: str = "needs_review"
    last_checked: str = field(default_factory=lambda: datetime.now(timezone.utc).date().isoformat())
    source_url: str = ""
    notes: str = ""

    def to_row(self) -> dict[str, str]:
        raw = asdict(self)
        out: dict[str, str] = {}
        for key in PRICE_COLUMNS:
            value = raw[key]
            if isinstance(value, Decimal):
                out[key] = format(value, "f")
            elif value is None:
                out[key] = ""
            elif isinstance(value, bool):
                out[key] = "true" if value else "false"
            else:
                out[key] = str(value)
        return out
