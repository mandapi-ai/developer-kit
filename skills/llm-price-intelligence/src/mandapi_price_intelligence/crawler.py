from __future__ import annotations

from decimal import DecimalException

from .adapters import adapter_for
from .fetch import PublicFetcher
from .models import Evidence, PriceRecord, SourceSpec


def _market_matches(source: SourceSpec, market: str) -> bool:
    if market == "global":
        return True
    if market == "brazil":
        return source.market_scope.lower() == "brazil" or source.brazil_relevance != "global_reference"
    return source.market_scope.lower() == market.lower()


def crawl_sources(
    sources: list[SourceSpec],
    *,
    user_agent: str,
    timeout_seconds: int,
    market: str,
) -> tuple[list[PriceRecord], list[Evidence]]:
    records: list[PriceRecord] = []
    evidence: list[Evidence] = []
    fetcher = PublicFetcher(user_agent=user_agent, timeout_seconds=timeout_seconds)
    try:
        for source in sources:
            if not source.enabled or not _market_matches(source, market):
                continue
            fetched = fetcher.fetch(source)
            evidence.append(fetched.evidence)
            if not fetched.evidence.ok:
                continue
            adapter = adapter_for(source.adapter)
            try:
                parsed = adapter.parse(source, fetched)
                records.extend(parsed)
                fetched.evidence.record_count = len(parsed)
                fetched.evidence.parser_status = "profile_only" if source.adapter == "profile_only" else ("parsed" if parsed else "no_supported_prices")
            except (ValueError, TypeError, KeyError, AttributeError, DecimalException) as exc:
                fetched.evidence.parser_status = "parse_error"
                fetched.evidence.error = f"{type(exc).__name__}: {exc}"
    finally:
        fetcher.close()
    return records, evidence
