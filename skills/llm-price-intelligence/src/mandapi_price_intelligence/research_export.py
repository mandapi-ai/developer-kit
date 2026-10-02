"""Local-only, reproducible research exports from a validated crawl snapshot."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

from .matching import MatchedSample, build_matched_sample, write_matched_sample
from .validate import validate_csv


SOURCE_COVERAGE_COLUMNS = [
    "source_id", "source_url", "fetched_at", "http_status", "response_sha256",
    "adapter", "parser_status", "record_count", "error",
]

METHODOLOGY = """# Methodology

This is a dated collection of public seller prices, not a guarantee of a future bill or
a complete catalog of every seller's models. Each observation retains its source URL;
`source-coverage.csv` contains fetch time, HTTP status, response SHA-256 and parser status.

Missing is not zero. A free access tier is a separate product from a paid retail token
offer. Promotion is not permanent standard pricing. Seller is not automatically the
model creator. Peak/off-peak is a time band, not a context tier. BRL conversion is
derived unless the seller itself publishes BRL. No currency conversion is performed.
Cross-currency price comparisons require an explicit dated FX source.

A model match requires explicit or conservatively documented identity evidence in
the accompanying `model-aliases.yaml`. Matching is seller scoped and exact on the seller model ID.
Similar names, previews, dated snapshots, modified routes and unresolved aliases do
not silently merge. A matched model needs at least two distinct sellers; context or
service tiers from one seller do not increase its seller count. Matching means the
public catalog claims the same model ID, not that backend serving was audited.

A retail API price is a time-indexed observation, not a permanent model attribute.
`prices.csv` preserves the 25-column V2 layout. `offer-details.csv` retains structured
service, time, cache and promotion dimensions keyed by `record_id`; every sidecar
row must match the snapshot and its exact source fetch timestamp in `evidence.jsonl`.
`has_brazil_seller` means a mapped offer from a source with `market_scope=Brazil`;
a Portuguese-language global seller alone does not satisfy that field. HTML candidate
prices can remain `needs_review`; `public_source` means extraction from a public
structured or dedicated deterministic source, not independent billing verification.
`matched-observations.csv` retains original currency and long-format offers. No
cross-currency min/max/spread is calculated. `unresolved-aliases.csv` explicitly
marks unmatched seller IDs as `unresolved`; they are excluded from matched offers.
"""


def write_source_coverage(evidence_path: str | Path, out_path: str | Path) -> None:
    rows = []
    with Path(evidence_path).open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"evidence.jsonl line {line_no}: invalid JSON") from exc
            rows.append({
                "source_id": item.get("source_id", ""),
                "source_url": item.get("url", ""),
                "fetched_at": item.get("fetched_at", ""),
                "http_status": item.get("status_code") or "",
                "response_sha256": item.get("sha256") or "",
                "adapter": item.get("adapter", ""),
                "parser_status": item.get("parser_status", ""),
                "record_count": item.get("record_count", 0),
                "error": item.get("error") or "",
            })
    with Path(out_path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SOURCE_COVERAGE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def export_matched(
    snapshot_dir: str | Path, out_dir: str | Path, alias_path: str | Path,
) -> MatchedSample:
    snapshot = Path(snapshot_dir)
    errors = validate_csv(snapshot / "prices.csv")
    if errors:
        raise ValueError(f"Invalid prices.csv: {errors[0]}")
    out = Path(out_dir)
    if any((out / name).exists() for name in (
        "matched-observations.csv", "matched-summary.csv", "unresolved-aliases.csv"
    )):
        raise ValueError("Matched output already exists; choose a new directory")
    sample = build_matched_sample(
        snapshot / "prices.csv", alias_path, snapshot / "offer-details.csv"
    )
    write_matched_sample(out, sample)
    return sample


def export_hf_v3(
    snapshot_dir: str | Path, out_dir: str | Path, alias_path: str | Path,
) -> MatchedSample:
    snapshot = Path(snapshot_dir)
    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError("Hugging Face V3 output already exists; choose a new directory")
    for filename in ("prices.csv", "providers.csv", "offer-details.csv", "evidence.jsonl"):
        if not (snapshot / filename).is_file():
            raise ValueError(f"Snapshot is missing {filename}")
    errors = validate_csv(snapshot / "prices.csv")
    if errors:
        raise ValueError(f"Invalid prices.csv: {errors[0]}")
    sample = build_matched_sample(
        snapshot / "prices.csv", alias_path, snapshot / "offer-details.csv"
    )
    out.mkdir(parents=True, exist_ok=True)
    for filename in ("prices.csv", "providers.csv", "offer-details.csv"):
        shutil.copyfile(snapshot / filename, out / filename)
    shutil.copyfile(alias_path, out / "model-aliases.yaml")
    write_matched_sample(out, sample)
    write_source_coverage(snapshot / "evidence.jsonl", out / "source-coverage.csv")
    (out / "methodology.md").write_text(METHODOLOGY, encoding="utf-8")
    (out / "README.md").write_text(
        "# MandAPI LLM Pricing Observatory — AI API Prices in Brazil\n\n"
        "A dated, reproducible view of public LLM API pricing, with BRL pricing from "
        "Brazil-focused gateways and original USD/CNY observations where published. "
        "It supports analysis of OpenRouter alternatives and gateway pricing without "
        "implicit currency conversion.\n\n"
        "`prices.csv` keeps the V2 raw seller observations; `offer-details.csv` holds "
        "service, context, cache and time dimensions. `matched-observations.csv` and "
        "`matched-summary.csv` contain only conservatively mapped model identities "
        "seen at two or more sellers. `source-coverage.csv` tracks fetch and parser "
        "outcomes. `unresolved-aliases.csv` lists seller IDs without a verified "
        "mapping. `model-aliases.yaml` records the identity evidence. See "
        "`methodology.md` for limitations and matching rules.\n\n"
        "This package was generated locally. Review `needs_review` observations "
        "before research publication.\n",
        encoding="utf-8",
    )
    return sample
