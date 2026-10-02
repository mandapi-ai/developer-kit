"""The crawl timestamp belongs to the fetched source, not the adapter clock."""

from mandapi_price_intelligence import crawler
from mandapi_price_intelligence.fetch import FetchResult
from mandapi_price_intelligence.models import Evidence, PriceRecord, SourceSpec


def _source(source_id: str) -> SourceSpec:
    return SourceSpec(
        id=source_id,
        platform=source_id,
        enabled=True,
        adapter="fixture",
        pricing_url=f"https://example.test/{source_id}",
        platform_type="gateway",
        source_type="competitor_public",
        default_currency="USD",
        market_scope="Brazil",
        brazil_relevance="direct_brl",
        openai_compatible=True,
    )


def _record(source_id: str) -> PriceRecord:
    return PriceRecord(
        record_id=source_id,
        model_id="example-model",
        canonical_model_id="example-model",
        model_name="Example Model",
        model_family="example",
        model_provider="Example",
        platform=source_id,
        platform_type="gateway",
        source_type="competitor_public",
        currency="USD",
        last_checked="2026-09-30",
    )


def test_crawl_stamps_each_successful_record_from_its_source_evidence(monkeypatch):
    sources = [_source("first"), _source("failed"), _source("second")]
    timestamps = {
        "first": "2026-10-02T10:11:12+00:00",
        "failed": "2026-10-02T10:11:13+00:00",
        "second": "2026-10-02T10:11:14+00:00",
    }
    parsed_records = {source.id: _record(source.id) for source in sources}
    closed = []

    class OfflineFetcher:
        def __init__(self, *, user_agent, timeout_seconds):
            pass

        def fetch(self, source):
            return FetchResult(
                text="fixture",
                json_data=None,
                evidence=Evidence(
                    source_id=source.id,
                    platform=source.platform,
                    url=source.pricing_url,
                    fetched_at=timestamps[source.id],
                    status_code=200,
                    sha256="fixture-hash",
                    adapter=source.adapter,
                    ok=True,
                ),
            )

        def close(self):
            closed.append(True)

    class OfflineAdapter:
        def parse(self, source, fetched):
            if source.id == "failed":
                raise ValueError("fixture parse failure")
            return [parsed_records[source.id]]

    monkeypatch.setattr(crawler, "PublicFetcher", OfflineFetcher)
    monkeypatch.setattr(crawler, "adapter_for", lambda name: OfflineAdapter())

    records, evidence = crawler.crawl_sources(
        sources, user_agent="offline", timeout_seconds=1, market="brazil"
    )

    assert [record.record_id for record in records] == ["first", "second"]
    assert [record.observed_at for record in records] == [timestamps["first"], timestamps["second"]]
    assert all(record.last_checked == "2026-09-30" for record in records)
    assert parsed_records["failed"].observed_at == ""
    assert [item.parser_status for item in evidence] == ["parsed", "parse_error", "parsed"]
    assert [item.record_count for item in evidence] == [1, 0, 1]
    assert closed == [True]
