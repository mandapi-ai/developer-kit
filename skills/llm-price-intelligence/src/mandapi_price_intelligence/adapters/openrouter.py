from __future__ import annotations

import re

from .base import Adapter
from ..fetch import FetchResult
from ..models import PriceRecord, SourceSpec
from ..normalize import (
    canonicalize_model_id,
    infer_model_family,
    infer_model_provider,
    per_token_to_per_million,
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


class OpenRouterAdapter(Adapter):
    def parse(self, source: SourceSpec, fetched: FetchResult) -> list[PriceRecord]:
        payload = fetched.json_data
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            return []

        out: list[PriceRecord] = []
        for item in payload["data"]:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or "").strip()
            if not model_id:
                continue
            pricing = item.get("pricing") or {}
            if not isinstance(pricing, dict):
                continue
            if all(per_token_to_per_million(pricing.get(k)) is None for k in ("prompt", "completion", "input_cache_read", "input_cache_write", "cache_read", "cache_write")):
                continue
            name = str(item.get("name") or model_id)
            context_length = item.get("context_length")
            canonical = canonicalize_model_id(model_id)
            cache_read = pricing.get("input_cache_read")
            if cache_read is None:
                cache_read = pricing.get("cache_read")
            cache_write = pricing.get("input_cache_write")
            if cache_write is None:
                cache_write = pricing.get("cache_write")

            token_rates = [per_token_to_per_million(pricing.get(k)) for k in ("prompt", "completion")]
            extra_charges = [per_token_to_per_million(pricing.get(k)) for k in ("image", "request", "audio", "input_audio", "output_audio")]
            if all(value is None or value == 0 for value in token_rates) and any(value is not None and value > 0 for value in extra_charges):
                continue

            out.append(
                PriceRecord(
                    record_id=f"openrouter-{_slug(model_id)}",
                    model_id=model_id,
                    canonical_model_id=canonical,
                    model_name=name,
                    model_family=infer_model_family(model_id, name),
                    model_provider=infer_model_provider(model_id, name),
                    platform=source.platform,
                    platform_type=source.platform_type,
                    source_type=source.source_type,
                    currency="USD",
                    input_per_1m=per_token_to_per_million(pricing.get("prompt")),
                    output_per_1m=per_token_to_per_million(pricing.get("completion")),
                    cache_read_per_1m=per_token_to_per_million(cache_read),
                    cache_write_per_1m=per_token_to_per_million(cache_write),
                    context_tier="standard",
                    context_limit_tokens=int(context_length) if isinstance(context_length, int) else None,
                    pricing_variant="listed_route",
                    price_scope="retail_price",
                    market_scope=source.market_scope,
                    brazil_relevance=source.brazil_relevance,
                    openai_compatible=source.openai_compatible,
                    verification_status="public_source",
                    source_url=fetched.evidence.url or source.pricing_url,
                    notes="Parsed from OpenRouter public model catalog API; per-token USD converted to per-1M-token USD. Non-token charges are excluded; consult source for full billing.",
                )
            )
        return out
