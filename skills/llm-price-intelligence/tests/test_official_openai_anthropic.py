"""Small fabricated official-page shapes; no copied third-party page snapshots."""

import hashlib
from decimal import Decimal

import pytest

from mandapi_price_intelligence.adapters.official_openai_anthropic import (
    AnthropicOfficialAdapter,
    OpenAIOfficialAdapter,
)
from mandapi_price_intelligence.fetch import FetchResult
from mandapi_price_intelligence.models import Evidence, SourceSpec


def source(adapter, platform):
    return SourceSpec(
        id=adapter, platform=platform, enabled=True, adapter=adapter,
        pricing_url=f"https://{adapter}.example.test/pricing",
        platform_type="official", source_type="official", default_currency="USD",
        market_scope="Global", brazil_relevance="global_reference",
        openai_compatible=adapter == "openai_official", unit="per_1m_tokens",
    )


def fetched(spec, document):
    return FetchResult(
        text=document, json_data=None,
        evidence=Evidence(
            source_id=spec.id, platform=spec.platform, url=spec.pricing_url,
            fetched_at="2026-10-02T10:20:30+00:00", status_code=200,
            sha256=hashlib.sha256(document.encode()).hexdigest(),
            adapter=spec.adapter, ok=True,
            content_type="text/markdown" if document.startswith("#") else "text/html",
        ),
    )


OPENAI_HEADER = (
    "| Model | Short context input | Short context cached input | Short context cache writes | "
    "Short context output | Long context input | Long context cached input | "
    "Long context cache writes | Long context output |"
)


def openai_doc(*sections, promotion=False):
    text = "# Pricing\n\nFlagship models\n\nPrices per 1M tokens.\n\n"
    for tier, rows in sections:
        text += f"### {tier.capitalize()} pricing data\n\n{OPENAI_HEADER}\n"
        text += "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        text += "\n".join(rows) + "\n\n"
    if promotion:
        text += "GPT-5.6 Sol’s promotional pricing is available at least through November 21, 2026.\n"
    return text


def test_openai_preserves_service_context_cache_and_promotion():
    spec = source("openai_official", "OpenAI")
    doc = openai_doc(
        ("standard", [
            "| gpt-6-sol | $2.00 | $0.20 | $2.50 | $10.00 | $4.00 | $0.40 | $5.00 | $15.00 |",
            "| gpt-5.6-sol | $4.00 | $0.40 | $5.00 | $20.00 | - | - | - | - |",
            "| gpt-5.5 (<272K context length) | $5.00 | $0.50 | - | $30.00 | $10.00 | $1.00 | - | $45.00 |",
        ]),
        ("batch", [
            "| gpt-6-sol | $1.00 | $0.10 | $1.25 | $5.00 | $2.00 | $0.20 | $2.50 | $7.50 |",
        ]),
        promotion=True,
    )
    rows = OpenAIOfficialAdapter().parse(spec, fetched(spec, doc))
    assert len(rows) == 7
    assert len({row.record_id for row in rows}) == len(rows)
    by = {(row.model_id, row.service_tier, row.context_tier): row for row in rows}
    base = by["gpt-6-sol", "standard", "short_context"]
    long = by["gpt-6-sol", "standard", "long_context"]
    batch = by["gpt-6-sol", "batch", "short_context"]
    assert (base.input_per_1m, base.output_per_1m, base.cache_read_per_1m,
            base.cache_write_per_1m) == tuple(map(Decimal, ("2", "10", "0.2", "2.5")))
    assert long.input_per_1m == Decimal("4") and long.output_per_1m == Decimal("15")
    assert batch.input_per_1m == Decimal("1") and batch.pricing_variant == "batch:short_context"
    assert base.source_url == spec.pricing_url and base.observed_at == "2026-10-02T10:20:30+00:00"
    assert base.model_creator == "OpenAI" and base.seller_model_id == "gpt-6-sol"
    assert all(row.verification_status == "public_source" and row.currency == "USD" for row in rows)
    assert by["gpt-5.5", "standard", "short_context"].context_threshold_tokens == 272000
    assert by["gpt-5.5", "standard", "long_context"].cache_write_per_1m is None
    assert by["gpt-5.6-sol", "standard", "short_context"].promotion_status == "promotion"
    assert by["gpt-5.6-sol", "standard", "short_context"].effective_end == ""


def test_openai_missing_is_not_zero_and_only_explicit_context_is_emitted():
    spec = source("openai_official", "OpenAI")
    doc = openai_doc(("standard", [
        "| gpt-test | $0 | - | - | $1 | - | - | - | - |",
    ]))
    rows = OpenAIOfficialAdapter().parse(spec, fetched(spec, doc))
    assert len(rows) == 1
    assert rows[0].input_per_1m == 0
    assert rows[0].cache_read_per_1m is None
    assert rows[0].cache_write_per_1m is None
    assert rows[0].context_tier == "short_context"


def test_openai_rejects_changed_header_and_conflicting_duplicate():
    spec = source("openai_official", "OpenAI")
    changed = openai_doc(("standard", ["| gpt-test | $1 | - | - | $2 | - | - | - | - | "]))
    changed = changed.replace("Long context output", "Long context total price")
    with pytest.raises(ValueError, match="header changed"):
        OpenAIOfficialAdapter().parse(spec, fetched(spec, changed))
    duplicate = openai_doc(("standard", [
        "| gpt-test | $1 | - | - | $2 | - | - | - | - |",
        "| gpt-test | $3 | - | - | $2 | - | - | - | - |",
    ]))
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        OpenAIOfficialAdapter().parse(spec, fetched(spec, duplicate))


def test_openai_html_fallback_keeps_tab_service_identity():
    spec = source("openai_official", "OpenAI")
    html = '''<div id="content-switcher-latest-pricing"><div class="content-switcher-panes">
    <div data-value="standard"><table>
    <tr><th></th><th colspan="4">Short context</th><th colspan="4">Long context</th></tr>
    <tr><th>Model</th><th>Input</th><th>Cached input</th><th>Cache writes</th><th>Output</th>
    <th>Input</th><th>Cached input</th><th>Cache writes</th><th>Output</th></tr>
    <tr><td>gpt-test</td><td>$1</td><td>-</td><td>-</td><td>$2</td>
    <td>$3</td><td>-</td><td>-</td><td>$4</td></tr></table></div></div></div>'''
    rows = OpenAIOfficialAdapter().parse(spec, fetched(spec, html))
    assert len(rows) == 2
    assert {row.context_tier for row in rows} == {"short_context", "long_context"}


def anthropic_doc(*, standard_rows=None, batch_rows=None, fast_rows=None):
    if standard_rows is None:
        standard_rows = [
            '<tr><td><a href="/docs/en/models/opus-5-5/overview">Claude Opus 5.5</a></td>'
            '<td>$4 / MTok</td><td>$20 / MTok</td><td>$5 / MTok</td>'
            '<td>$8 / MTok</td><td>$0.20 / MTok</td></tr>',
            '<tr><td><a href="/docs/en/models/haiku-4-5/overview">Claude Haiku 4.5</a></td>'
            '<td>$1 / MTok</td><td>$5 / MTok</td><td>$1.25 / MTok</td>'
            '<td>$2 / MTok</td><td>$0.10 / MTok</td></tr>',
        ]
    if batch_rows is None:
        batch_rows = [
            '<tr><td><a href="/docs/en/models/opus-5-5/overview">Claude Opus 5.5</a></td>'
            '<td>$2 / MTok</td><td>$10 / MTok</td></tr>',
        ]
    if fast_rows is None:
        fast_rows = [
            '<tr><td>Claude Opus 5.5</td><td>$8 / MTok</td><td>$40 / MTok</td></tr>',
        ]
    return (
        '<p>All prices are in USD.</p><h2 id="model-pricing">Model pricing</h2>'
        '<table><tr><th>Model</th><th>Base tokens</th><th>Prompt caching</th></tr>'
        '<tr><th>Name</th><th>Input</th><th>Output</th><th>5m writes</th>'
        '<th>1h writes</th><th>Hits and refreshes</th></tr>'
        + "".join(standard_rows) + '</table>'
        '<h3 id="batch-processing">Batch processing</h3><table>'
        '<tr><th>Model</th><th>Batch tokens</th></tr>'
        '<tr><th>Name</th><th>Input</th><th>Output</th></tr>'
        + "".join(batch_rows) + '</table>'
        + (('<h3 id="fast-mode-pricing">Fast mode pricing</h3><table>'
            '<tr><th>Model</th><th>Input</th><th>Output</th></tr>'
            + "".join(fast_rows) + '</table>') if fast_rows else '')
    )


def test_anthropic_separates_cache_write_durations_and_service_tiers():
    spec = source("anthropic_official", "Anthropic")
    rows = AnthropicOfficialAdapter().parse(spec, fetched(spec, anthropic_doc()))
    assert len(rows) == 4
    assert len({row.record_id for row in rows}) == len(rows)
    by = {(row.model_id, row.service_tier): row for row in rows}
    opus = by["claude-opus-5-5", "standard"]
    assert (opus.input_per_1m, opus.output_per_1m, opus.cache_read_per_1m) == (
        Decimal("4"), Decimal("20"), Decimal("0.20"))
    assert opus.cache_write_5m_per_1m == Decimal("5")
    assert opus.cache_write_1h_per_1m == Decimal("8")
    assert opus.cache_write_per_1m == opus.cache_write_5m_per_1m
    assert by["claude-opus-5-5", "batch"].input_per_1m == Decimal("2")
    assert by["claude-opus-5-5", "batch"].cache_read_per_1m is None
    assert by["claude-opus-5-5", "fast"].input_per_1m == Decimal("8")
    assert all(row.model_creator == "Anthropic" and row.verification_status == "public_source"
               for row in rows)
    # The public pricing page names a rolling pre-4.6 alias, not a dated snapshot.
    assert by["claude-haiku-4-5", "standard"].seller_model_id == "claude-haiku-4-5"


def test_anthropic_missing_cache_is_null_and_unlinked_legacy_row_is_skipped():
    spec = source("anthropic_official", "Anthropic")
    linked = ('<tr><td><a href="/docs/en/models/sonnet-5-5/overview">Claude Sonnet 5.5</a></td>'
              '<td>$2 / MTok</td><td>$10 / MTok</td><td>-</td><td>-</td><td>-</td></tr>')
    legacy = ('<tr><td>Claude Opus 4.1</td><td>$15 / MTok</td><td>$75 / MTok</td>'
              '<td>$18.75 / MTok</td><td>$30 / MTok</td><td>$1.50 / MTok</td></tr>')
    rows = AnthropicOfficialAdapter().parse(spec, fetched(
        spec, anthropic_doc(standard_rows=[linked, legacy], batch_rows=[], fast_rows=[])))
    assert len(rows) == 1 and rows[0].model_id == "claude-sonnet-5-5"
    assert rows[0].cache_read_per_1m is None and rows[0].cache_write_5m_per_1m is None
    assert rows[0].cache_write_1h_per_1m is None


def test_anthropic_rejects_malformed_and_conflicting_duplicate_rows():
    spec = source("anthropic_official", "Anthropic")
    malformed = anthropic_doc().replace("Hits and refreshes", "Cached input and output")
    with pytest.raises(ValueError, match="header changed"):
        AnthropicOfficialAdapter().parse(spec, fetched(spec, malformed))
    duplicate = ('<tr><td><a href="/docs/en/models/opus-5-5/overview">Claude Opus 5.5</a></td>'
                 '<td>$9 / MTok</td><td>$20 / MTok</td><td>$5 / MTok</td>'
                 '<td>$8 / MTok</td><td>$0.20 / MTok</td></tr>')
    doc = anthropic_doc(standard_rows=[
        '<tr><td><a href="/docs/en/models/opus-5-5/overview">Claude Opus 5.5</a></td>'
        '<td>$4 / MTok</td><td>$20 / MTok</td><td>$5 / MTok</td>'
        '<td>$8 / MTok</td><td>$0.20 / MTok</td></tr>', duplicate],
        batch_rows=[], fast_rows=[])
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        AnthropicOfficialAdapter().parse(spec, fetched(spec, doc))
