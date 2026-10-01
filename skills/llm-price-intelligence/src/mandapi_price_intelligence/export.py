from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from .models import PRICE_COLUMNS, Evidence, PriceRecord, SourceSpec


PROVIDER_COLUMNS = [
    "platform", "platform_type", "source_type", "website", "pricing_url",
    "default_currency", "country_focus", "openai_compatible", "brazil_focus",
    "public_numeric_pricing", "source_url", "notes",
]


def write_prices(path: str | Path, records: list[PriceRecord]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PRICE_COLUMNS)
        writer.writeheader()
        for record in sorted(records, key=lambda r: (r.platform.lower(), r.canonical_model_id, r.pricing_variant)):
            writer.writerow(record.to_row())


def write_providers(path: str | Path, sources: list[SourceSpec]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PROVIDER_COLUMNS)
        writer.writeheader()
        for s in sorted((x for x in sources if x.enabled), key=lambda x: x.platform.lower()):
            writer.writerow({
                "platform": s.platform,
                "platform_type": s.platform_type,
                "source_type": s.source_type,
                "website": s.extra.get("website", ""),
                "pricing_url": s.pricing_url,
                "default_currency": s.default_currency,
                "country_focus": s.market_scope,
                "openai_compatible": "true" if s.openai_compatible else "false",
                "brazil_focus": "true" if s.market_scope.lower() == "brazil" else "false",
                "public_numeric_pricing": "unknown" if s.adapter != "profile_only" else "no/partial",
                "source_url": s.pricing_url,
                "notes": f"Adapter: {s.adapter}. Registry metadata; numeric price rows require source evidence.",
            })


def write_evidence(path: str | Path, evidence: list[Evidence]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in evidence:
            f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")


def write_summary(path: str | Path, records: list[PriceRecord], evidence: list[Evidence]) -> None:
    ok = sum(1 for e in evidence if e.ok)
    failed = len(evidence) - ok
    verified = sum(1 for r in records if r.verification_status == "public_source")
    review = sum(1 for r in records if r.verification_status == "needs_review")
    platforms = len({r.platform for r in records})
    brl = sum(1 for r in records if r.currency == "BRL")
    lines = [
        "# LLM Price Intelligence Crawl Summary",
        "",
        f"- Sources attempted: **{len(evidence)}**",
        f"- Sources fetched successfully: **{ok}**",
        f"- Sources failed: **{failed}**",
        f"- Price records: **{len(records)}**",
        f"- Platforms with numeric candidate records: **{platforms}**",
        f"- Structured/public-source records: **{verified}**",
        f"- Needs-review records: **{review}**",
        f"- BRL records: **{brl}**",
        "",
        "Generic HTML records are candidates only. Review them before adding them to a published research snapshot.",
    ]
    lines += ["", "| Source | HTTP | Parser | Models with prices | Price records |", "| --- | --- | --- | --- | --- |"]
    lines += [f"| {e.source_id} | {e.status_code or 'network error'} | {e.parser_status} | {len({r.model_id for r in records if r.platform == e.platform})} | {e.record_count} |" for e in evidence]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
