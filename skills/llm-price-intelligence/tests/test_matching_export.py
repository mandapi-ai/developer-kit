from __future__ import annotations

import csv
import json
from decimal import Decimal

import pytest

from mandapi_price_intelligence.export import write_offer_details, write_prices, write_providers
from mandapi_price_intelligence.matching import build_matched_sample, load_aliases, write_matched_sample
from mandapi_price_intelligence.models import PriceRecord
from mandapi_price_intelligence.research_export import export_hf_v3


def record(seller: str, model_id: str, variant: str, currency: str = "USD", **prices):
    return PriceRecord(
        record_id=f"{seller}-{model_id}-{variant}", model_id=model_id,
        canonical_model_id="gpt-4o-mini", model_name="GPT-4o mini", model_family="GPT",
        model_provider="OpenAI", platform=seller,
        platform_type="official" if seller == "OpenAI" else "gateway",
        source_type="official" if seller == "OpenAI" else "competitor_public",
        currency=currency, pricing_variant=variant, service_tier=variant,
        market_scope="Brazil" if seller == "MandAPI" else "Global",
        brazil_relevance="direct_brl" if seller == "MandAPI" else "global_reference",
        source_url="https://example.org/pricing", last_checked="2026-10-02",
        observed_at="2026-10-02T00:00:00+00:00", verification_status="public_source",
        **prices,
    )


def fixture(tmp_path, rows, *, with_mandapi=False):
    snap = tmp_path / "snapshot"
    snap.mkdir()
    write_prices(snap / "prices.csv", rows)
    write_offer_details(snap / "offer-details.csv", rows)
    write_providers(snap / "providers.csv", [])
    (snap / "evidence.jsonl").write_text("".join(json.dumps({
        "source_id": seller.lower(), "platform": seller,
        "url": "https://example.org/pricing",
        "fetched_at": "2026-10-02T00:00:00+00:00", "status_code": 200,
        "sha256": "a" * 64, "adapter": seller.lower(),
        "parser_status": "parsed", "record_count": sum(row.platform == seller for row in rows),
    }) + "\n" for seller in sorted({row.platform for row in rows})), encoding="utf-8")
    aliases = tmp_path / "aliases.yaml"
    entries = [
        "  - seller: OpenRouter\n    seller_model_id: openai/gpt-4o-mini\n"
        "    canonical_model_id: gpt-4o-mini\n    model_creator: OpenAI\n"
        "    confidence: seller_namespace\n    evidence: https://openrouter.ai/openai/gpt-4o-mini\n"
    ]
    if with_mandapi:
        entries.append(
            "  - seller: MandAPI\n    seller_model_id: gpt-4o-mini\n"
            "    canonical_model_id: gpt-4o-mini\n    model_creator: OpenAI\n"
            "    confidence: manual_verified\n    evidence: https://mandapi.com/pricing\n"
        )
    aliases.write_text("aliases:\n" + "".join(entries), encoding="utf-8")
    return snap, aliases


def test_distinct_sellers_official_reference_original_currencies_and_missing(tmp_path):
    rows = [
        record("OpenAI", "gpt-4o-mini", "standard", input_per_1m=Decimal("0.15")),
        record("OpenAI", "gpt-4o-mini", "batch", input_per_1m=Decimal("0.075")),
        record("OpenRouter", "openai/gpt-4o-mini", "listed", input_per_1m=Decimal("0.20")),
        record("MandAPI", "gpt-4o-mini", "retail", "BRL", input_per_1m=Decimal("1.00")),
        record("OpenRouter", "openai/gpt-4o-mini:extended", "variant", input_per_1m=Decimal("0.21")),
    ]
    snapshot, aliases = fixture(tmp_path, rows, with_mandapi=True)
    sample = build_matched_sample(snapshot / "prices.csv", aliases, snapshot / "offer-details.csv")
    assert len(sample.summary) == 1
    assert sample.summary[0]["seller_count"] == "3"
    assert sample.summary[0]["official_reference_count"] == "1"
    assert sample.summary[0]["currencies"] == "BRL;USD"
    assert sample.summary[0]["has_brazil_seller"] == "true"
    assert sample.summary[0]["has_mandapi"] == "true"
    assert ("OpenRouter", "openai/gpt-4o-mini:extended") in sample.unresolved
    write_matched_sample(tmp_path / "matched", sample)
    with (tmp_path / "matched/unresolved-aliases.csv").open(encoding="utf-8-sig", newline="") as f:
        unresolved_rows = list(csv.DictReader(f))
    assert unresolved_rows == [{
        "seller": "OpenRouter", "seller_model_id": "openai/gpt-4o-mini:extended",
        "canonical_model_id": "", "match_status": "unresolved",
    }]
    assert len(sample.observations) == 4
    assert all(row["has_official_reference"] == "true" and row["official_seller"] == "OpenAI" for row in sample.observations)
    assert next(row for row in sample.observations if row["seller"] == "OpenAI")["match_confidence"] == "exact"
    assert next(row for row in sample.observations if row["seller"] == "OpenRouter")["match_confidence"] == "seller_namespace"
    assert next(row for row in sample.observations if row["seller"] == "MandAPI")["match_confidence"] == "manual_verified"
    assert next(row for row in sample.observations if row["seller"] == "MandAPI")["currency"] == "BRL"
    assert next(row for row in sample.observations if row["seller"] == "OpenAI")["output_per_1m"] == ""
    assert not any("spread" in key or "min_price" in key for key in sample.summary[0])


def test_one_seller_with_two_context_rows_is_not_a_match(tmp_path):
    rows = [
        record("OpenAI", "gpt-4o-mini", "standard", input_per_1m=Decimal("1")),
        record("OpenAI", "gpt-4o-mini", "batch", input_per_1m=Decimal("0.5")),
    ]
    snapshot, aliases = fixture(tmp_path, rows)
    sample = build_matched_sample(snapshot / "prices.csv", aliases, snapshot / "offer-details.csv")
    assert sample.summary == []
    assert sample.observations == []


def test_documented_alias_matches_only_the_exact_seller_id(tmp_path):
    rows = [
        record("OpenAI", "gpt-4o-mini", "standard", input_per_1m=Decimal("0.15")),
        record("OpenRouter", "openai/gpt-4o-mini-alias", "listed", input_per_1m=Decimal("0.20")),
        record("OpenRouter", "openai/gpt-4o-mini-alias:version2", "preview", input_per_1m=Decimal("0.21")),
    ]
    snapshot, aliases = fixture(tmp_path, rows)
    aliases.write_text("aliases:\n"
        "  - seller: OpenRouter\n    seller_model_id: openai/gpt-4o-mini-alias\n"
        "    canonical_model_id: gpt-4o-mini\n    model_creator: OpenAI\n"
        "    confidence: documented_alias\n"
        "    evidence: https://openrouter.ai/openai/gpt-4o-mini-alias\n", encoding="utf-8")
    sample = build_matched_sample(snapshot / "prices.csv", aliases, snapshot / "offer-details.csv")
    assert len(sample.observations) == 2
    assert next(row for row in sample.observations if row["seller"] == "OpenRouter")["match_confidence"] == "documented_alias"
    assert ("OpenRouter", "openai/gpt-4o-mini-alias:version2") in sample.unresolved


def test_alias_registry_rejects_wildcards_and_unsupported_confidence(tmp_path):
    path = tmp_path / "aliases.yaml"
    path.write_text(
        "aliases:\n  - seller: X\n    seller_model_id: openai/*\n"
        "    canonical_model_id: gpt-4o-mini\n    model_creator: OpenAI\n"
        "    confidence: probably_same\n    evidence: https://example.org/model\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_aliases(path)
    path.write_text(path.read_text(encoding="utf-8").replace("probably_same", "seller_namespace"), encoding="utf-8")
    with pytest.raises(ValueError, match="wildcards"):
        load_aliases(path)


def test_local_hf_package_preserves_v2_and_evidence(tmp_path):
    rows = [
        record("OpenAI", "gpt-4o-mini", "standard", input_per_1m=Decimal("0.15")),
        record("OpenRouter", "openai/gpt-4o-mini", "listed", input_per_1m=Decimal("0.20")),
    ]
    snapshot, aliases = fixture(tmp_path, rows)
    out = tmp_path / "huggingface-v3"
    sample = export_hf_v3(snapshot, out, aliases)
    assert len(sample.summary) == 1
    assert sample.summary[0]["has_brazil_seller"] == "false"
    assert {"README.md", "prices.csv", "providers.csv", "offer-details.csv",
            "matched-observations.csv", "matched-summary.csv", "methodology.md",
            "source-coverage.csv", "unresolved-aliases.csv",
            "model-aliases.yaml"}.issubset({p.name for p in out.iterdir()})
    with (out / "source-coverage.csv").open(encoding="utf-8-sig", newline="") as f:
        coverage = list(csv.DictReader(f))
    assert coverage[0]["response_sha256"] == "a" * 64
    assert coverage[0]["parser_status"] == "parsed"
    assert "Cross-currency" in (out / "methodology.md").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        export_hf_v3(snapshot, out, aliases)


def test_official_creator_comes_from_detail_not_sales_channel(tmp_path):
    official = record("Google AI Studio", "gemini-3.1-pro-preview", "paid", input_per_1m=Decimal("1"))
    official.platform_type = "official"
    official.model_creator = "Google"
    routed = record("OpenRouter", "google/gemini-3.1-pro-preview", "listed", input_per_1m=Decimal("1.1"))
    snapshot, aliases = fixture(tmp_path, [official, routed])
    aliases.write_text("aliases:\n"
        "  - seller: OpenRouter\n    seller_model_id: google/gemini-3.1-pro-preview\n"
        "    canonical_model_id: gemini-3.1-pro-preview\n    model_creator: Google\n"
        "    confidence: seller_namespace\n"
        "    evidence: https://openrouter.ai/google/gemini-3.1-pro-preview\n", encoding="utf-8")
    sample = build_matched_sample(snapshot / "prices.csv", aliases, snapshot / "offer-details.csv")
    assert sample.summary[0]["model_creator"] == "Google"
    assert all(row["model_creator"] == "Google" for row in sample.observations)


def test_offer_details_must_match_snapshot_and_fetch_evidence(tmp_path):
    rows = [record("OpenAI", "gpt-4o-mini", "standard", input_per_1m=Decimal("0.15"))]
    snapshot, aliases = fixture(tmp_path, rows)
    details_path = snapshot / "offer-details.csv"
    with pytest.raises(ValueError, match="missing offer-details"):
        build_matched_sample(snapshot / "prices.csv", aliases, snapshot / "absent.csv")
    with details_path.open(encoding="utf-8-sig", newline="") as stream:
        details = list(csv.DictReader(stream))
    columns = list(details[0])

    def rewrite():
        with details_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerows(details)

    details[0]["record_id"] = "stale-record"
    rewrite()
    with pytest.raises(ValueError, match="record_ids do not match"):
        build_matched_sample(snapshot / "prices.csv", aliases, details_path)
    details[0]["record_id"] = rows[0].record_id
    details[0]["seller_model_id"] = "different-model"
    rewrite()
    with pytest.raises(ValueError, match="seller_model_id mismatch"):
        build_matched_sample(snapshot / "prices.csv", aliases, details_path)
    details[0]["seller_model_id"] = rows[0].model_id
    details[0]["observed_at"] = "2026-10-01T00:00:00+00:00"
    rewrite()
    with pytest.raises(ValueError, match="does not match fetch evidence"):
        build_matched_sample(snapshot / "prices.csv", aliases, details_path)


def test_hf_export_requires_offer_details(tmp_path):
    snapshot, aliases = fixture(tmp_path, [record("OpenAI", "gpt-4o-mini", "standard")])
    (snapshot / "offer-details.csv").unlink()
    with pytest.raises(ValueError, match="missing offer-details"):
        export_hf_v3(snapshot, tmp_path / "huggingface-v3", aliases)
