from pathlib import Path

from mandapi_price_intelligence.adapters.generic_html import GenericHtmlTableAdapter
from mandapi_price_intelligence.fetch import FetchResult
from mandapi_price_intelligence.models import Evidence, SourceSpec


def test_generic_table_is_needs_review():
    html = (Path(__file__).parent / "fixtures" / "pricing-table.html").read_text(encoding="utf-8")
    source = SourceSpec(
        id="fixture",
        platform="Fixture",
        enabled=True,
        adapter="generic_html",
        pricing_url="https://example.test/pricing",
        platform_type="gateway",
        source_type="competitor_public",
        default_currency="BRL",
        market_scope="Brazil",
        brazil_relevance="direct_brl",
        openai_compatible=True,
        unit="per_1m_tokens",
    )
    fetched = FetchResult(
        text=html,
        json_data=None,
        evidence=Evidence(
            source_id="fixture", platform="Fixture", url=source.pricing_url,
            fetched_at="2026-10-01T00:00:00Z", status_code=200,
            sha256="abc", adapter="generic_html", ok=True, content_type="text/html",
        ),
    )
    rows = GenericHtmlTableAdapter().parse(source, fetched)
    assert len(rows) == 2
    assert rows[0].verification_status == "needs_review"
    assert str(rows[0].input_per_1m) == "0.40"
    assert str(rows[0].output_per_1m) == "2.00"
