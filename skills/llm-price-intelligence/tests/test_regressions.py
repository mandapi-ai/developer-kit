"""Offline regression fixtures are synthesized, not copied provider pages."""
import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from decimal import Decimal

import httpx
import pytest
import yaml

from mandapi_price_intelligence import cli, crawler
from mandapi_price_intelligence.adapters.generic_html import GenericHtmlTableAdapter
from mandapi_price_intelligence.adapters.openrouter import OpenRouterAdapter
from mandapi_price_intelligence.adapters.profile_only import ProfileOnlyAdapter
from mandapi_price_intelligence.adapters.provider_html import KunavoAdapter, RoteiaAdapter, RunAPIAdapter, TokenRecargaAdapter
from mandapi_price_intelligence.diff import build_diff_markdown
from mandapi_price_intelligence.export import write_providers
from mandapi_price_intelligence.fetch import FetchResult, PublicFetcher
from mandapi_price_intelligence.models import Evidence, SourceSpec
from mandapi_price_intelligence.registry import load_registry


def source(adapter="generic_html", **changes):
    fields = dict(id="fixture", platform="Fixture", enabled=True, adapter=adapter,
        pricing_url="https://example.test/pricing", platform_type="gateway",
        source_type="competitor_public", default_currency="USD", market_scope="Brazil",
        brazil_relevance="direct_brl", openai_compatible=True, unit="per_1m_tokens")
    fields.update(changes)
    return SourceSpec(**fields)


def fetched(spec, html="", payload=None):
    return FetchResult(text=html, json_data=payload, evidence=Evidence(
        source_id=spec.id, platform=spec.platform, url=spec.pricing_url,
        fetched_at="2026-10-01T00:00:00Z", status_code=200,
        sha256=hashlib.sha256(html.encode()).hexdigest(), adapter=spec.adapter,
        ok=True, content_type="application/json" if payload else "text/html"))


def test_roteia_catalog_preserves_ids_brl_and_missing_long_tier_cache():
    spec = source("roteia")
    catalog = [
        {"id": "anthropic/Claude_Test", "name": "Claude Test", "pricingUnit": "million_tokens",
         "providerName": "Anthropic", "priceInBrlPerM": 1.25, "priceOutBrlPerM": 6,
         "cacheReadBrlPerM": 0.1, "contextWindowTokens": 200000,
         "longContextPricingBrl": {"thresholdTokens": 100000, "priceOutBrlPerM": 9}},
        {"id": "free-model", "pricingUnit": "million_tokens", "priceInBrlPerM": 0},
        {"id": "missing-model", "pricingUnit": "million_tokens", "priceInBrlPerM": None},
        {"id": "image-model", "pricingUnit": "image", "priceInBrlPerM": 5}]
    html = "<script>const ignored = 1;</script><script>window.__ROTEIA_PUBLIC_CATALOG__ = " + json.dumps(catalog) + ";</script>"
    rows = RoteiaAdapter().parse(spec, fetched(spec, html))
    assert len(rows) == 3
    base, long, free = rows
    assert base.model_id == long.model_id == "anthropic/Claude_Test"
    assert base.canonical_model_id == "claude-test"
    assert base.currency == long.currency == free.currency == "BRL"
    assert base.input_per_1m == Decimal("1.25")
    assert base.cache_read_per_1m == Decimal("0.1")
    assert base.context_limit_tokens == 200000
    assert long.context_tier == ">100000"
    assert long.input_per_1m is None and long.output_per_1m == Decimal("9")
    assert long.cache_read_per_1m is None and long.cache_write_per_1m is None
    assert free.input_per_1m == 0 and free.output_per_1m is None
    assert free.to_row()["input_per_1m"] == "0" and free.to_row()["output_per_1m"] == ""
    assert all(row.verification_status == "needs_review" for row in rows)
    assert base.record_id != long.record_id


def runapi_row(model, variant="", unit="/ 1M tokens"):
    return f'<tr data-pricing-table-row><td>{model}<span>{variant}</span></td><td>OpenAI</td><td>$0.40 {unit}</td><td>$2.00 {unit}</td><td>$40.00 {unit}</td><td>$200.00 {unit}</td><td>99%</td></tr>'


def test_runapi_uses_provider_prices_and_retains_protocol_variants():
    spec = source("runapi")
    html = '<table><tr><th colspan="4">RunAPI</th><th colspan="3">Official</th></tr><tr><th scope="col">Model</th><th scope="col">Provider</th><th scope="col">RunAPI in/M</th><th scope="col">RunAPI out/M</th><th scope="col">Official in/M</th><th scope="col">Official out/M</th><th scope="col">Savings</th></tr>'
    html += runapi_row("gpt-test", "Chat") + runapi_row("gpt-test", "Responses")
    html += runapi_row("gpt-test", "Chat") + runapi_row("image-test", "Image", "/ image")
    html += '<table><tr><th scope="col">Official in/M</th></tr>' + runapi_row("official-only", "Chat") + "</table>"
    rows = RunAPIAdapter().parse(spec, fetched(spec, html))
    assert len(rows) == 2
    assert {row.pricing_variant for row in rows} == {"Chat", "Responses"}
    assert len({row.record_id for row in rows}) == 2
    assert all(row.model_id == "gpt-test" and row.currency == "USD" for row in rows)
    assert all(row.input_per_1m == Decimal("0.40") and row.output_per_1m == Decimal("2.00") for row in rows)
    assert all(row.verification_status == "needs_review" for row in rows)


def test_kunavo_joins_cache_without_counting_another_offer():
    spec = source("kunavo")
    html = '<table><tr><th>Model</th><th>Provider</th><th>Input price</th><th>Output price</th><th>Billing unit</th><th>vs Official</th></tr><tr><td><a href="/models/anthropic/claude-test">Claude Test</a></td><td>Anthropic</td><td>$1.25</td><td>$6.00</td><td>per 1M tokens</td><td>50%</td></tr><tr><td><a href="/models/image-model">Image Model</a></td><td>OpenAI</td><td>$0.25</td><td>-</td><td>per image</td><td>50%</td></tr></table><table><tr><th>Model</th><th>Input</th><th>Cache read</th><th>Cache write</th><th>Ratio</th></tr><tr><td><div>Claude Test</div></td><td>$1.25</td><td>$0.10</td><td>-</td><td>10%</td></tr><tr><td><div>Cache Only</div></td><td>$0.40</td><td>$0.10</td><td>$0.50</td><td>25%</td></tr></table>'
    rows = KunavoAdapter().parse(spec, fetched(spec, html))
    assert len(rows) == 1
    row = rows[0]
    assert row.model_id == "anthropic/claude-test"
    assert row.cache_read_per_1m == Decimal("0.10") and row.cache_write_per_1m is None
    assert row.input_per_1m == Decimal("1.25") and row.verification_status == "needs_review"


def test_tokenrecarga_keeps_brl_and_excludes_quote_cards():
    spec = source("tokenrecarga")
    html = '<a href="/precos/gpt-test"><h3>GPT Test</h3><code>openai/gpt-test</code><dl><dd>128K context</dd><dd>R$ 1,25 entrada / R$ 6,00 saída / 1M tokens</dd></dl></a><a href="/precos/quote-test"><h3>Quote Test</h3><code>quote-test</code><dd>Sob consulta / 1M tokens</dd></a><a href="/other"><h3>Unrelated</h3><code>other</code><dd>R$ 1 entrada R$ 2 saída / 1M tokens</dd></a>'
    rows = TokenRecargaAdapter().parse(spec, fetched(spec, html))
    assert len(rows) == 1
    assert rows[0].model_id == "openai/gpt-test"
    assert rows[0].input_per_1m == Decimal("1.25") and rows[0].output_per_1m == Decimal("6.00")
    assert rows[0].currency == "BRL" and "Tax excluded" in rows[0].notes
    assert rows[0].verification_status == "needs_review"


@pytest.mark.parametrize("payload", [None, [], {}, {"data": {}}, {"data": None}])
def test_openrouter_rejects_non_catalog_payload(payload):
    spec = source("openrouter")
    assert OpenRouterAdapter().parse(spec, fetched(spec, payload=payload)) == []


def test_openrouter_missing_is_not_zero_and_free_zero_survives():
    spec = source("openrouter")
    payload = {"data": [None, "bad", {}, {"id": "no-prices"}, {"id": "null", "pricing": None},
        {"id": "bad-pricing", "pricing": [1]},
        {"id": "invalid", "pricing": {"prompt": "NaN", "completion": "-1"}},
        {"id": "openai/paid-test", "pricing": {"prompt": "0.00000125", "completion": None,
            "input_cache_read": None, "cache_read": "0.0000001"}, "context_length": 128000},
        {"id": "free-test", "pricing": {"prompt": "0", "completion": 0}}]}
    rows = OpenRouterAdapter().parse(spec, fetched(spec, payload=payload))
    assert len(rows) == 2
    paid, free = rows
    assert paid.input_per_1m == Decimal("1.25") and paid.output_per_1m is None
    assert paid.cache_read_per_1m == Decimal("0.1") and paid.context_limit_tokens == 128000
    assert free.input_per_1m == free.output_per_1m == 0
    assert all(row.currency == "USD" and row.verification_status == "public_source" for row in rows)


@pytest.mark.parametrize("status", [403, 429, 503])
def test_fetch_http_errors_keep_status_and_body_hash(status):
    spec, body = source(), b"provider temporarily unavailable"
    fetcher = PublicFetcher(user_agent="offline-test")
    fetcher.client.close()
    fetcher.client = httpx.Client(transport=httpx.MockTransport(lambda request:
        httpx.Response(status, content=body, request=request, headers={"content-type": "text/plain"})))
    try:
        result = fetcher.fetch(spec)
    finally:
        fetcher.close()
    assert not result.evidence.ok and result.evidence.status_code == status
    assert result.evidence.sha256 == hashlib.sha256(body).hexdigest()
    assert result.evidence.error == f"HTTP {status}"
    assert result.text == "" and result.json_data is None


def test_profile_only_exports_provider_and_never_invents_prices(tmp_path):
    spec = source("profile_only", extra={"website": "https://example.test/"})
    assert ProfileOnlyAdapter().parse(spec, fetched(spec, "<p>$9.99 subscription</p>")) == []
    path = tmp_path / "providers.csv"
    write_providers(path, [spec, source(id="disabled", enabled=False)])
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1 and rows[0]["public_numeric_pricing"] == "no/partial"
    assert rows[0]["website"] == "https://example.test/" and rows[0]["brazil_focus"] == "true"


@pytest.mark.parametrize("mutation", [
    lambda raw: raw.update(sources={}),
    lambda raw: raw.update(sources=[None]),
    lambda raw: raw["sources"][0].pop("platform"),
    lambda raw: raw["sources"].append(dict(raw["sources"][0])),
    lambda raw: raw["sources"][0].update(adapter="made-up"),
    lambda raw: raw["sources"][0].update(enabled="true"),
    lambda raw: raw["sources"][0].update(openai_compatible=1),
    lambda raw: raw["sources"][0].update(pricing_url="file:///secret"),
    lambda raw: raw["sources"][0].update(default_currency="EUR"),
    lambda raw: raw["sources"][0].update(unit="per_image"),
    lambda raw: raw.update(default_timeout_seconds=0),
    lambda raw: raw.update(default_timeout_seconds=True),
])
def test_registry_rejects_malformed_entries(tmp_path, mutation):
    entry = asdict(source())
    entry.pop("extra")
    raw = {"sources": [entry]}
    mutation(raw)
    path = tmp_path / "sources.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        load_registry(path)


@pytest.mark.parametrize("name", ["prices.csv", "providers.csv", "evidence.jsonl", "crawl-summary.md"])
def test_crawl_rejects_snapshot_overwrite_before_fetching(tmp_path, monkeypatch, name):
    existing = tmp_path / name
    existing.write_text("preserve original snapshot", encoding="utf-8")
    def forbidden_fetch(*args, **kwargs):
        pytest.fail("Existing snapshot must be rejected before loading or fetching sources")
    monkeypatch.setattr(cli, "crawl_sources", forbidden_fetch)
    monkeypatch.setattr(cli, "load_registry", forbidden_fetch)
    args = argparse.Namespace(out=str(tmp_path), sources="unused", market="brazil")
    with pytest.raises(ValueError, match="Snapshot already exists"):
        cli.cmd_crawl(args)
    assert existing.read_text(encoding="utf-8") == "preserve original snapshot"
    assert list(tmp_path.iterdir()) == [existing]


def test_generic_code_id_and_cached_input_are_distinct():
    spec = source()
    html = '<table><tr><th>Model</th><th>Cached input</th><th>Input</th><th>Output</th><th>Billing unit</th></tr><tr><td>Friendly Name <code>openai/gpt-test</code></td><td>$0.10</td><td>$1.25</td><td>-</td><td>per 1M tokens</td></tr><tr><td><code>free-test</code></td><td>-</td><td>$0</td><td>$0</td><td>per 1M tokens</td></tr></table>'
    rows = GenericHtmlTableAdapter().parse(spec, fetched(spec, html))
    assert len(rows) == 2
    assert rows[0].model_id == "openai/gpt-test"
    assert rows[0].model_name == "Friendly Name openai/gpt-test"
    assert rows[0].input_per_1m == Decimal("1.25") and rows[0].cache_read_per_1m == Decimal("0.10")
    assert rows[0].output_per_1m is None
    assert rows[1].input_per_1m == rows[1].output_per_1m == 0
    assert all(row.verification_status == "needs_review" for row in rows)


@pytest.mark.parametrize("input_price,output_price,unit", [
    ("$1 / 1k tokens", "$2 / 1k tokens", "per 1M tokens"),
    ("$0.001 per token", "$0.002 per token", "per 1M tokens"),
    ("$1 per image", "$2", "per 1M tokens"), ("$1", "$2", "per image"),
    ("$1", "R$ 2", "per 1M tokens"), ("$1 - 2", "Contact sales", "per 1M tokens"),
    ("Starting from $1", "-", "per 1M tokens"),
])
def test_generic_excludes_wrong_units_currencies_and_unpriced_ranges(input_price, output_price, unit):
    spec = source()
    html = f"<table><tr><th>Model</th><th>Input</th><th>Output</th><th>Unit</th></tr><tr><td>test</td><td>{input_price}</td><td>{output_price}</td><td>{unit}</td></tr></table>"
    assert GenericHtmlTableAdapter().parse(spec, fetched(spec, html)) == []


def test_diff_distinguishes_missing_from_zero(tmp_path):
    header = "platform,model_id,pricing_variant,context_tier,currency,input_per_1m,output_per_1m\n"
    old, new = tmp_path / "old.csv", tmp_path / "new.csv"
    old.write_text(header + "X,model,standard,,USD,,2\n", encoding="utf-8")
    new.write_text(header + "X,model,standard,,USD,0,2.0\n", encoding="utf-8")
    report = build_diff_markdown(old, new)
    assert "Price component changes: **1**" in report and "missing → 0" in report


def test_diff_unavailable_source_does_not_count_removed_offers(tmp_path):
    header = "platform,model_id,pricing_variant,context_tier,currency,input_per_1m,output_per_1m\n"
    old, new = tmp_path / "old.csv", tmp_path / "new.csv"
    old.write_text(header + "X,model,standard,,USD,1,2\n", encoding="utf-8")
    new.write_text(header, encoding="utf-8")
    (tmp_path / "evidence.jsonl").write_text(json.dumps({"platform": "X", "ok": False, "parser_status": "not_attempted"}) + "\n", encoding="utf-8")
    report = build_diff_markdown(old, new)
    assert "Removed offers: **0**" in report
    assert "Unobserved offers from unavailable sources: **1**" in report


def test_crawl_records_parse_error_and_continues(monkeypatch):
    bad, good, profile = source("roteia", id="bad"), source("openrouter", id="good"), source("profile_only", id="profile")
    closed = []
    results = {"bad": fetched(bad, '<script>window.__ROTEIA_PUBLIC_CATALOG__ = {"not": "a list"};</script>'),
        "good": fetched(good, payload={"data": [{"id": "free", "pricing": {"prompt": "0"}}]}),
        "profile": fetched(profile, "<p>No public numeric prices</p>")}
    class OfflineFetcher:
        def __init__(self, **kwargs):
            pass
        def fetch(self, spec):
            return results[spec.id]
        def close(self):
            closed.append(True)
    monkeypatch.setattr(crawler, "PublicFetcher", OfflineFetcher)
    records, evidence = crawler.crawl_sources([bad, good, profile], user_agent="offline", timeout_seconds=1, market="brazil")
    assert len(records) == 1 and records[0].input_per_1m == 0
    assert [item.parser_status for item in evidence] == ["parse_error", "parsed", "profile_only"]
    assert evidence[0].ok and evidence[0].record_count == 0 and "ValueError" in evidence[0].error
    assert closed == [True]


from mandapi_price_intelligence.adapters.api_catalog import APIMartAdapter, OminiGateAdapter


def test_roteia_standard_tier_has_explicit_upper_bound():
    spec = source("roteia")
    catalog = [{"id": "tier-model", "pricingUnit": "million_tokens",
        "priceInBrlPerM": 1, "priceOutBrlPerM": 2,
        "longContextPricingBrl": {"thresholdTokens": 100000, "priceInBrlPerM": 3}}]
    rows = RoteiaAdapter().parse(spec, fetched(spec,
        "<script>window.__ROTEIA_PUBLIC_CATALOG__ = " + json.dumps(catalog) + ";</script>"))
    assert [row.context_tier for row in rows] == ["<=100000", ">100000"]


def test_kunavo_same_display_name_preserves_ids_without_ambiguous_cache_join():
    spec = source("kunavo")
    html = '<table><tr><th>Model</th><th>Provider</th><th>Input price</th><th>Output price</th><th>Billing unit</th><th>vs Official</th></tr><tr><td><a href="/models/model-v1">Shared Name</a></td><td>Provider</td><td>$1</td><td>$2</td><td>per 1M tokens</td><td>50%</td></tr><tr><td><a href="/models/model-v2">Shared Name</a></td><td>Provider</td><td>$3</td><td>$4</td><td>per 1M tokens</td><td>50%</td></tr></table><table><tr><th>Model</th><th>Input</th><th>Cache read</th><th>Cache write</th><th>Ratio</th></tr><tr><td><div>Shared Name</div></td><td>$1</td><td>$0.1</td><td>$0.2</td><td>10%</td></tr></table>'
    rows = KunavoAdapter().parse(spec, fetched(spec, html))
    assert {row.model_id for row in rows} == {"model-v1", "model-v2"}
    assert all(row.cache_read_per_1m is None and row.cache_write_per_1m is None for row in rows)


def test_apimart_uses_explicit_base_per_million_and_excludes_member_discounts():
    spec = source("apimart")
    payload = {"data": {"models": {
        "llm": [
            {"id": "openai/paid-test", "name": "Paid", "pricing": {
                "unit": "usd_per_million_tokens", "rates": {"input": "1.25", "output": None, "cached_input": "0.1"},
                "effective": {"input": "0.50", "output": "1.00"},
                "member": {"input": "0.20", "output": "0.50"}},
             "token_pricing": {"group": {"input": "0.75", "output": "1.50"}}},
            {"id": "free-test", "pricing": {"unit": "usd_per_million_tokens", "rates": {"input": 0, "output": "0"}}},
            {"id": "null-test", "pricing": {"unit": "usd_per_million_tokens", "rates": {"input": None, "output": None}}},
            {"id": "wrong-unit", "pricing": {"unit": "usd_per_image", "rates": {"input": 8}}},
            {"id": "effective-only", "pricing": {"unit": "usd_per_million_tokens", "effective": {"input": "0.5"}}}],
        "image": [{"id": "image-test", "pricing": {"unit": "usd_per_image", "rates": {"input": 7}}}]}}}
    rows = APIMartAdapter().parse(spec, fetched(spec, payload=payload))
    assert len(rows) == 2
    paid, free = rows
    assert paid.model_id == "openai/paid-test" and paid.input_per_1m == Decimal("1.25")
    assert paid.output_per_1m is None and paid.cache_read_per_1m == Decimal("0.1")
    assert free.input_per_1m == free.output_per_1m == 0
    assert all(row.pricing_variant == "listed_base" and row.currency == "USD" and row.verification_status == "public_source" for row in rows)


def test_apimart_context_tiers_do_not_inherit_missing_cache_components():
    spec = source("apimart")
    payload = {"data": {"models": {"llm": [{"id": "tier-test", "pricing": {
        "unit": "usd_per_million_tokens", "limits": {"max_input_tokens": 500000},
        "tiers": [
            {"up_to_input_tokens": 100000, "input": "1", "output": "2", "cached_input": "0"},
            {"up_to_input_tokens": 200000, "input": "3", "cache_write": None},
            {"up_to_input_tokens": None, "input": "5", "cached_input": None, "cache_write": "7"}]},
        "effective": {"input": "0.01"}}]}}}
    rows = APIMartAdapter().parse(spec, fetched(spec, payload=payload))
    assert [row.context_tier for row in rows] == ["<=100000", "100000<tokens<=200000", ">200000"]
    assert [row.input_per_1m for row in rows] == [Decimal("1"), Decimal("3"), Decimal("5")]
    assert rows[0].cache_read_per_1m == 0
    assert rows[1].output_per_1m is None and rows[1].cache_read_per_1m is None and rows[1].cache_write_per_1m is None
    assert rows[2].cache_read_per_1m is None and rows[2].cache_write_per_1m == Decimal("7")
    assert len({row.record_id for row in rows}) == 3
    assert all(row.context_limit_tokens == 500000 for row in rows)


def test_apimart_fallback_model_tiers_do_not_use_group_tiers():
    spec = source("apimart")
    payload = {"data": {"models": {"llm": [{"id": "fallback-test",
        "pricing": {"unit": "usd_per_million_tokens"},
        "token_pricing": {
            "model": {"tiers": [{"up_to_input_tokens": None, "input": "1.25"}]},
            "group": {"tiers": [{"up_to_input_tokens": None, "input": "0.25"}]}}}]}}}
    rows = APIMartAdapter().parse(spec, fetched(spec, payload=payload))
    assert len(rows) == 1 and rows[0].input_per_1m == Decimal("1.25")


@pytest.mark.parametrize("uppers", [[200000, 100000], [100000, 100000], [0]])
def test_apimart_rejects_non_increasing_context_tiers(uppers):
    spec = source("apimart")
    payload = {"data": {"models": {"llm": [{"id": "bad-tier", "pricing": {
        "unit": "usd_per_million_tokens",
        "tiers": [{"up_to_input_tokens": upper, "input": "1"} for upper in uppers]}}]}}}
    with pytest.raises(ValueError, match="invalid context tiers"):
        APIMartAdapter().parse(spec, fetched(spec, payload=payload))


def test_ominigate_per_million_not_scaled_and_non_text_models_excluded():
    spec = source("ominigate")
    payload = {"data": [
        {"id": "paid-test", "output_modalities": ["text"], "pricing": {"prompt": "1.25", "completion": None, "input_cache_read": "0.1"}},
        {"id": "free-test", "output_modalities": ["text"], "pricing": {"prompt": 0, "completion": "0"}},
        {"id": "missing-test", "output_modalities": ["text"], "pricing": {"prompt": None}},
        {"id": "image-test", "output_modalities": ["image"], "pricing": {"prompt": "2", "completion": "3"}},
        {"id": "unknown-modality", "pricing": {"prompt": "4"}},
        {"id": "invalid-test", "output_modalities": ["text"], "pricing": {"prompt": "NaN", "completion": -1}},
        {"id": "boolean-test", "output_modalities": ["text"], "pricing": {"prompt": True}}]}
    rows = OminiGateAdapter().parse(spec, fetched(spec, payload=payload))
    assert len(rows) == 2
    paid, free = rows
    assert paid.input_per_1m == Decimal("1.25") and paid.output_per_1m is None
    assert paid.cache_read_per_1m == Decimal("0.1") and paid.cache_write_per_1m is None
    assert free.input_per_1m == free.output_per_1m == 0
    assert all(row.currency == "USD" and row.verification_status == "public_source" and row.pricing_variant == "catalog_list" for row in rows)


def test_ominigate_tiers_keep_partial_cache_and_exclude_one_hour_variant():
    spec = source("ominigate")
    payload = {"data": [{"id": "tier-test", "output_modalities": ["text"], "context_length": 500000,
        "pricing": {"prompt": "1", "completion": "2", "input_cache_read": "0.1",
            "input_cache_write": "1.5", "input_cache_write_1h": "9",
            "tiers": [
                {"threshold": 100000, "prompt": "3", "completion": None, "input_cache_read": None},
                {"threshold": 200000, "prompt": "5", "input_cache_write": "6", "input_cache_write_1h": "12"}]}}]}
    rows = OminiGateAdapter().parse(spec, fetched(spec, payload=payload))
    assert [row.context_tier for row in rows] == ["<=100000", "100000<tokens<=200000", ">200000"]
    assert [row.input_per_1m for row in rows] == [Decimal("1"), Decimal("3"), Decimal("5")]
    assert rows[0].cache_write_per_1m == Decimal("1.5")
    assert rows[1].output_per_1m is None and rows[1].cache_read_per_1m is None and rows[1].cache_write_per_1m is None
    assert rows[2].cache_write_per_1m == Decimal("6") and rows[2].cache_read_per_1m is None
    assert len({row.record_id for row in rows}) == 3
    assert all(row.context_limit_tokens == 500000 for row in rows)


@pytest.mark.parametrize("adapter,payload", [
    (APIMartAdapter, None), (APIMartAdapter, {"data": {"models": {"llm": {}}}}),
    (OminiGateAdapter, None), (OminiGateAdapter, {"data": {}}),
])
def test_public_api_adapters_reject_wrong_catalog_shape(adapter, payload):
    spec = source()
    with pytest.raises(ValueError):
        adapter().parse(spec, fetched(spec, payload=payload))


def test_generic_rejects_per_thousand_header_even_with_bare_cells():
    spec = source()
    html = '<table><tr><th>Model</th><th>Input / 1k tokens</th><th>Output / 1k tokens</th></tr><tr><td>test</td><td>1</td><td>2</td></tr></table>'
    assert GenericHtmlTableAdapter().parse(spec, fetched(spec, html)) == []


def test_generic_rejects_conflicting_currencies_inside_one_price_cell():
    spec = source()
    html = '<table><tr><th>Model</th><th>Input</th><th>Output</th></tr><tr><td>test</td><td>$1 / R$2</td><td>-</td></tr></table>'
    assert GenericHtmlTableAdapter().parse(spec, fetched(spec, html)) == []


def runapi_range_table(details=""):
    return ('<table><tr><th scope="col">Model</th><th scope="col">Provider</th>'
        '<th scope="col">RunAPI in/M</th><th scope="col">RunAPI out/M</th>'
        '<th scope="col">Official in/M</th><th scope="col">Official out/M</th><th scope="col">Savings</th></tr>'
        '<tr data-pricing-table-row><td>gpt-tier-test<span>Chat</span></td><td>OpenAI</td>'
        '<td>$1.20 - $2.40 / 1M tokens</td><td>$8.00 - $16.00 / 1M tokens</td>'
        '<td>$20.00 - $40.00 / 1M tokens</td><td>$80.00 - $160.00 / 1M tokens</td><td>90%</td></tr>'
        + details + '</table>')


def test_runapi_tier_details_preserve_labels_cache_and_partial_components():
    spec = source("runapi")
    details = '<tr data-pricing-table-details><td colspan="7"><dl>'
    rates = [
        ("Prompt < 272,001", "Input", "$1.20"),
        ("Prompt < 272,001", "Cached input", "$0.12"),
        ("Prompt < 272,001", "Cache write", "$1.50"),
        ("Prompt < 272,001", "Output", "$8.00"),
        ("Prompt >= 272,001", "Input", "$2.40"),
        ("Prompt >= 272,001", "Cached input", "$0.24"),
        ("Prompt >= 272,001", "Cache write", "-"),
        ("Prompt >= 272,001", "Output", "$16.00"),
    ]
    details += "".join(f'<div><dt>{tier.replace("<", "&lt;")} · {component}</dt><dd>{price} / 1M tokens</dd></div>'
        for tier, component, price in rates)
    details += '</dl></td></tr>'
    rows = RunAPIAdapter().parse(spec, fetched(spec, runapi_range_table(details)))
    assert len(rows) == 2
    low, high = rows
    assert [row.context_tier for row in rows] == ["Prompt < 272,001", "Prompt >= 272,001"]
    assert all(row.model_id == "gpt-tier-test" and row.pricing_variant == "Chat" for row in rows)
    assert low.input_per_1m == Decimal("1.20") and high.input_per_1m == Decimal("2.40")
    assert low.output_per_1m == Decimal("8.00") and high.output_per_1m == Decimal("16.00")
    assert low.cache_read_per_1m == Decimal("0.12") and high.cache_read_per_1m == Decimal("0.24")
    assert low.cache_write_per_1m == Decimal("1.50") and high.cache_write_per_1m is None
    assert len({row.record_id for row in rows}) == 2
    assert all(row.verification_status == "needs_review" and row.currency == "USD" for row in rows)


@pytest.mark.parametrize("details", [
    "",
    '<tr data-pricing-table-details><td colspan="7"><dl><div><dt>Context 272,001 · Input</dt><dd>$1.20 / 1M tokens</dd></div></dl></td></tr>',
    '<tr data-pricing-table-details><td colspan="7"><dl><div><dt>Prompt &lt; 272,001 · Input</dt><dd>$1.20 / image</dd></div></dl></td></tr>',
    '<tr data-pricing-table-details><td colspan="7"><dl><div><dt>Prompt &lt; 272,001 · Unknown</dt><dd>$1.20 / 1M tokens</dd></div></dl></td></tr>',
    '<tr data-pricing-table-details><td colspan="7"><dl><div><dt>Prompt &lt; 272,001 · Input</dt></div><div><dt>Prompt &lt; 272,001 · Output</dt><dd>- / 1M tokens</dd></div></dl></td></tr>',
])
def test_runapi_range_headline_is_not_flattened_without_usable_tier_details(details):
    spec = source("runapi")
    assert RunAPIAdapter().parse(spec, fetched(spec, runapi_range_table(details))) == []


def test_generic_unavailable_price_with_token_unit_remains_missing():
    spec = source()
    html = '<table><tr><th>Model</th><th>Input</th><th>Output</th></tr><tr><td>missing-test</td><td>- / 1M tokens</td><td>N/A / 1M tokens</td></tr><tr><td>partial-test</td><td>$0 / 1M tokens</td><td>- / 1M tokens</td></tr></table>'
    rows = GenericHtmlTableAdapter().parse(spec, fetched(spec, html))
    assert len(rows) == 1 and rows[0].model_id == "partial-test"
    assert rows[0].input_per_1m == 0 and rows[0].output_per_1m is None
