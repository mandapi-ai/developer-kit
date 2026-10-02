"""Small synthetic official-page fragments: no third-party page mirror is stored."""

import hashlib
from decimal import Decimal

import pytest

from mandapi_price_intelligence.adapters.official_google_deepseek import DeepSeekAdapter, GoogleAiStudioAdapter
from mandapi_price_intelligence.fetch import FetchResult
from mandapi_price_intelligence.models import Evidence, SourceSpec


def _source(adapter: str) -> SourceSpec:
    return SourceSpec(
        id=adapter, platform="Google AI Studio" if adapter == "google-ai-studio" else "DeepSeek",
        enabled=True, adapter=adapter, pricing_url=f"https://example.test/{adapter}/pricing",
        platform_type="official", source_type="official", default_currency="USD",
        market_scope="Global", brazil_relevance="global_reference",
        openai_compatible=adapter == "deepseek", unit="per_1m_tokens",
    )


def _fetched(source: SourceSpec, html: str) -> FetchResult:
    return FetchResult(html, None, Evidence(
        source_id=source.id, platform=source.platform, url=source.pricing_url,
        fetched_at="2026-10-01T12:00:00Z", status_code=200,
        sha256=hashlib.sha256(html.encode()).hexdigest(), adapter=source.adapter,
        ok=True, content_type="text/html",
    ))


def _gemini_table(input_paid: str, output_paid: str, cache_paid: str, *, header: str = "Paid Tier, per 1M tokens in USD", free: str = "Free of charge") -> str:
    return f"""<table class="pricing-table"><thead><tr><th></th><th>Free Tier</th><th>{header}</th></tr></thead><tbody>
    <tr><td>Input price</td><td>{free}</td><td>{input_paid}</td></tr>
    <tr><td>Output price (including thinking tokens)</td><td>{free}</td><td>{output_paid}</td></tr>
    <tr><td>Context caching price</td><td>Not available</td><td>{cache_paid}</td></tr>
    </tbody></table>"""


def test_gemini_paid_service_context_dates_and_storage_are_separate():
    spec = _source("google-ai-studio")
    standard = _gemini_table(
        "$1.25, prompts &lt;= 200k tokens<br>$2.50, prompts &gt; 200k tokens",
        "$10.00, prompts &lt;= 200k tokens<br>$15.00, prompts &gt; 200k tokens",
        "$0.125, prompts &lt;= 200k tokens<br>$0.25, prompts &gt; 200k tokens<br>$4.50 / 1,000,000 tokens per hour (storage price)",
    )
    batch = _gemini_table(
        "$0.625, prompts &lt;= 200k tokens<br>$1.25, prompts &gt; 200k tokens",
        "$5.00, prompts &lt;= 200k tokens<br>$7.50, prompts &gt; 200k tokens",
        "$0.125, prompts &lt;= 200k tokens<br>$0.25, prompts &gt; 200k tokens",
        free="Not available",
    )
    page = f"<h2>Gemini 2.5 Pro</h2><em><code>gemini-2.5-pro</code></em><h3>Standard</h3>{standard}<h3>Batch</h3>{batch}"
    rows = GoogleAiStudioAdapter().parse(spec, _fetched(spec, page))
    assert len(rows) == 4
    by_key = {(row.service_tier, row.context_tier): row for row in rows}
    short = by_key[("standard", "<=200000")]
    long = by_key[("standard", ">200000")]
    assert short.input_per_1m == Decimal("1.25")
    assert long.output_per_1m == Decimal("15.00")
    assert short.cache_read_per_1m == Decimal("0.125")
    assert short.cache_storage_per_1m_hour == Decimal("4.50")
    assert short.context_threshold_tokens == 200000
    assert long.context_threshold_tokens == 200000
    assert short.context_limit_tokens is None
    assert by_key[("batch", "<=200000")].input_per_1m == Decimal("0.625")
    assert all(row.verification_status == "public_source" and row.currency == "USD" for row in rows)
    assert all(row.price_scope == "retail_price" and row.charge_type == "token" for row in rows)
    assert len({row.record_id for row in rows}) == 4


def test_gemini_uses_observed_date_and_never_treats_audio_or_free_as_text_retail():
    spec = _source("google-ai-studio")
    page = "<h2>Gemini 3.8 Flash</h2><em><code>gemini-3.8-flash</code></em><h3>Standard</h3>" + _gemini_table(
        "$0.75 through December 31, 2026.<br>$1.50 starting January 1, 2027.<br>$3.00 (audio)",
        "$3.75 through December 31, 2026.<br>$7.50 starting January 1, 2027.",
        "$0.075 through December 31, 2026.<br>$0.15 starting January 1, 2027.<br>$0.50 / 1,000,000 tokens per hour (storage price) through December 31, 2026.",
    )
    rows = GoogleAiStudioAdapter().parse(spec, _fetched(spec, page))
    assert len(rows) == 1
    row = rows[0]
    assert row.input_per_1m == Decimal("0.75")
    assert row.output_per_1m == Decimal("3.75")
    assert row.cache_storage_per_1m_hour == Decimal("0.50")
    assert row.effective_end == "2026-12-31"
    assert row.promotion_status == "time_limited"
    assert row.pricing_variant == "paid_standard"
    assert row.observed_at == "2026-10-01T12:00:00Z"


@pytest.mark.parametrize("page", [
    "<h2>Gemini 2.5 Flash</h2><em><code>gemini-2.5-flash</code></em><h3>Standard</h3>" + _gemini_table("Not available", "$2.50", "$0.03"),
    "<h2>Gemini 2.5 Flash</h2><em><code>gemini-2.5-flash</code></em><h3>Standard</h3>" + _gemini_table("$0.30", "$2.50", "$0.03", header="Paid Tier, per request"),
])
def test_gemini_missing_or_wrong_unit_does_not_yield_a_zero_price(page):
    spec = _source("google-ai-studio")
    with pytest.raises(ValueError):
        GoogleAiStudioAdapter().parse(spec, _fetched(spec, page))


def test_gemini_duplicate_offer_is_rejected():
    spec = _source("google-ai-studio")
    table = _gemini_table("$0.30", "$2.50", "$0.03")
    page = f"<h2>Gemini 2.5 Flash</h2><em><code>gemini-2.5-flash</code></em><h3>Standard</h3>{table}<h3>Standard</h3>{table}"
    with pytest.raises(ValueError, match="Duplicate Gemini offer"):
        GoogleAiStudioAdapter().parse(spec, _fetched(spec, page))


def test_gemini_grouped_usd_amount_is_not_truncated():
    spec = _source("google-ai-studio")
    page = "<h2>Gemini 3.8 Pro</h2><em><code>gemini-3.8-pro</code></em><h3>Standard</h3>" + _gemini_table(
        "$1,000.25, prompts &lt;= 200k tokens", "$2,000.50, prompts &lt;= 200k tokens", "$100.00",
    )
    rows = GoogleAiStudioAdapter().parse(spec, _fetched(spec, page))
    assert len(rows) == 1
    assert rows[0].input_per_1m == Decimal("1000.25")
    assert rows[0].output_per_1m == Decimal("2000.50")


@pytest.mark.parametrize("bad_amount", ["$1,00", "$1,0000", "$1.000,50"])
def test_gemini_malformed_grouped_usd_amount_is_rejected(bad_amount):
    spec = _source("google-ai-studio")
    page = "<h2>Gemini 3.8 Pro</h2><em><code>gemini-3.8-pro</code></em><h3>Standard</h3>" + _gemini_table(
        bad_amount, "$2.50", "$0.10",
    )
    with pytest.raises(ValueError, match="unsupported USD format"):
        GoogleAiStudioAdapter().parse(spec, _fetched(spec, page))


_DEEPSEEK_BASE = """<h1>Models &amp; Pricing</h1><p>The prices listed below are in units of per 1M tokens.</p>
<table><tr><td colspan="3">MODEL</td><td>deepseek-flash<sup>(1)</sup></td><td>deepseek-v4-pro</td></tr>
<tr><td colspan="3">MODEL VERSION</td><td>DeepSeek-V4.1-Flash</td><td>DeepSeek-V4-Pro-0813</td></tr>
<tr><td colspan="3">CONTEXT LENGTH</td><td colspan="2">1M</td></tr>
<tr><td rowspan="6">PRICING</td><td rowspan="2">1M INPUT TOKENS<br>(CACHE HIT)</td><td>OFF-PEAK</td><td>$0.003</td><td>$0.022</td></tr>
<tr><td>PEAK</td><td>$0.006</td><td>$0.044</td></tr>
<tr><td rowspan="2">1M INPUT TOKENS<br>(CACHE MISS)</td><td>OFF-PEAK</td><td>$0.15</td><td>$0.66</td></tr>
<tr><td>PEAK</td><td>$0.3</td><td>$1.32</td></tr>
<tr><td rowspan="2">1M OUTPUT TOKENS</td><td>OFF-PEAK</td><td>$0.6</td><td>$1.98</td></tr>
<tr><td>PEAK</td><td>$1.2</td><td>$3.96</td></tr></table>
<p>Peak hours are 01:00 - 04:00 and 06:00 - 10:00 UTC, Monday through Friday, excluding Chinese public holidays. All other hours are off-peak, including weekends and Chinese public holidays in full.</p>"""


def test_deepseek_peak_offpeak_and_cache_are_distinct():
    spec = _source("deepseek")
    rows = DeepSeekAdapter().parse(spec, _fetched(spec, _DEEPSEEK_BASE))
    assert len(rows) == 4
    by_key = {(row.model_id, row.pricing_variant): row for row in rows}
    offpeak = by_key[("deepseek-flash", "paid_off_peak")]
    peak = by_key[("deepseek-flash", "paid_peak")]
    assert offpeak.input_per_1m == Decimal("0.15")
    assert offpeak.cache_read_per_1m == Decimal("0.003")
    assert offpeak.output_per_1m == Decimal("0.6")
    assert peak.input_per_1m == Decimal("0.3")
    assert peak.cache_read_per_1m == Decimal("0.006")
    assert "01:00 - 04:00" in peak.time_band and "UTC" in peak.time_band
    assert "weekends" in offpeak.time_band
    assert peak.context_limit_tokens == 1_000_000
    assert peak.model_name == "DeepSeek-V4.1-Flash"
    assert len({row.record_id for row in rows}) == 4
    assert all(row.verification_status == "public_source" for row in rows)


def test_deepseek_missing_numeric_remains_missing():
    spec = _source("deepseek")
    page = _DEEPSEEK_BASE.replace("<td>$0.003</td>", "<td>-</td>")
    rows = DeepSeekAdapter().parse(spec, _fetched(spec, page))
    offpeak = next(row for row in rows if row.model_id == "deepseek-flash" and row.pricing_variant == "paid_off_peak")
    assert offpeak.cache_read_per_1m is None
    assert offpeak.input_per_1m == Decimal("0.15")


@pytest.mark.parametrize("row", [
    '<tr><td>PEAK</td><td>$0.006</td><td>$0.044</td></tr>',
    '<tr><td>PEAK</td><td>$0.3</td><td>$1.32</td></tr>',
    '<tr><td>PEAK</td><td>$1.2</td><td>$3.96</td></tr>',
])
def test_deepseek_incomplete_charge_band_is_rejected(row):
    spec = _source("deepseek")
    page = _DEEPSEEK_BASE.replace(row, "")
    assert page != _DEEPSEEK_BASE
    with pytest.raises(ValueError, match="Incomplete DeepSeek pricing rows"):
        DeepSeekAdapter().parse(spec, _fetched(spec, page))


@pytest.mark.parametrize("amount", ["$0.15", "$0.6"])
def test_deepseek_missing_input_or_output_amount_is_rejected(amount):
    spec = _source("deepseek")
    page = _DEEPSEEK_BASE.replace(f"<td>{amount}</td>", "<td>-</td>")
    assert page != _DEEPSEEK_BASE
    with pytest.raises(ValueError, match="input/output price is unavailable"):
        DeepSeekAdapter().parse(spec, _fetched(spec, page))


def test_deepseek_malformed_schedule_or_conflicting_duplicate_fails():
    spec = _source("deepseek")
    with pytest.raises(ValueError, match="schedule"):
        DeepSeekAdapter().parse(spec, _fetched(spec, _DEEPSEEK_BASE.replace("Peak hours are", "Discount hours are")))
    conflicting = _DEEPSEEK_BASE.replace("</table>", "<tr><td>1M OUTPUT TOKENS</td><td>PEAK</td><td>$9.99</td><td>$3.96</td></tr></table>")
    with pytest.raises(ValueError, match="Conflicting DeepSeek"):
        DeepSeekAdapter().parse(spec, _fetched(spec, conflicting))
