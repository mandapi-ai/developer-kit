"""Conservative, seller-scoped identity matching for dated price observations."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import yaml


OFFICIAL_SELLERS = frozenset({"OpenAI", "Anthropic", "Google AI Studio", "DeepSeek"})
OFFICIAL_CREATORS = {
    "OpenAI": "OpenAI", "Anthropic": "Anthropic",
    "Google AI Studio": "Google", "DeepSeek": "DeepSeek",
}
CONFIDENCES = frozenset({"exact", "documented_alias", "seller_namespace", "manual_verified"})
OBSERVATION_COLUMNS = [
    "snapshot_date", "canonical_model_id", "model_name", "model_creator", "seller",
    "seller_type", "seller_model_id", "currency", "input_per_1m", "output_per_1m",
    "cache_read_per_1m", "cache_write_per_1m", "cache_write_5m_per_1m",
    "cache_write_1h_per_1m", "cache_storage_per_1m_hour", "context_tier",
    "context_limit_tokens", "context_threshold_tokens", "service_tier", "time_band",
    "pricing_variant", "promotion_status", "effective_start", "effective_end",
    "charge_type", "modality", "verification_status", "source_url", "observed_at",
    "has_official_reference", "official_seller", "match_status", "match_confidence",
    "record_id", "market_scope", "brazil_relevance",
]
SUMMARY_COLUMNS = [
    "canonical_model_id", "model_name", "model_creator", "seller_count",
    "numeric_offer_count", "official_reference_count", "gateway_count", "currencies",
    "has_official_reference", "has_openrouter", "has_brazil_seller", "has_mandapi",
]
UNRESOLVED_COLUMNS = ["seller", "seller_model_id", "canonical_model_id", "match_status"]


@dataclass(frozen=True)
class Alias:
    seller: str
    seller_model_id: str
    canonical_model_id: str
    model_creator: str
    confidence: str
    evidence: str


@dataclass
class MatchedSample:
    observations: list[dict[str, str]]
    summary: list[dict[str, str]]
    unresolved: list[tuple[str, str]]


def default_alias_path() -> Path:
    local = Path(__file__).resolve().parents[2] / "data" / "model-aliases.yaml"
    return local if local.exists() else Path(__file__).with_name("model-aliases.yaml")


def load_aliases(path: str | Path) -> dict[tuple[str, str], Alias]:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid alias registry YAML: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("aliases"), list):
        raise ValueError("Alias registry needs an 'aliases' list")
    aliases: dict[tuple[str, str], Alias] = {}
    for index, item in enumerate(raw["aliases"]):
        if not isinstance(item, dict):
            raise ValueError(f"Alias {index}: expected mapping")
        required = ("seller", "seller_model_id", "canonical_model_id", "model_creator", "confidence", "evidence")
        if any(not isinstance(item.get(k), str) or not item[k].strip() for k in required):
            raise ValueError(f"Alias {index}: missing seller-scoped identity evidence")
        alias = Alias(*(item[k].strip() for k in required))
        if alias.confidence not in CONFIDENCES:
            raise ValueError(f"Alias {index}: unsupported confidence {alias.confidence}")
        if not alias.evidence.startswith("https://"):
            raise ValueError(f"Alias {index}: evidence must be a public HTTPS URL")
        if any(c in alias.seller_model_id for c in "*?"):
            raise ValueError(f"Alias {index}: wildcards are not allowed")
        key = (alias.seller.casefold(), alias.seller_model_id)
        if key in aliases:
            raise ValueError(f"Duplicate seller alias: {key}")
        aliases[key] = alias
    return aliases


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _details_by_record(path: str | Path | None) -> dict[str, dict[str, str]]:
    if path is None or not Path(path).is_file():
        raise ValueError("Snapshot is missing offer-details.csv")
    result = {}
    for row in _read_csv(path):
        key = row.get("record_id", "")
        if not key or key in result:
            raise ValueError("offer-details.csv has missing or duplicate record_id")
        result[key] = row
    return result


def _evidence_times(path: Path) -> dict[tuple[str, str], set[str]]:
    if not path.is_file():
        raise ValueError("Snapshot is missing evidence.jsonl")
    result: dict[tuple[str, str], set[str]] = {}
    with path.open(encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"evidence.jsonl line {line_no}: invalid JSON") from exc
            platform, url, fetched_at = (row.get(key, "") for key in ("platform", "url", "fetched_at"))
            if platform and url and fetched_at:
                result.setdefault((platform, url), set()).add(fetched_at)
    return result


def build_matched_sample(
    prices_path: str | Path,
    alias_path: str | Path,
    details_path: str | Path | None = None,
) -> MatchedSample:
    aliases = load_aliases(alias_path)
    details = _details_by_record(details_path)
    prices = _read_csv(prices_path)
    evidence_times = _evidence_times(Path(prices_path).parent / "evidence.jsonl")
    price_ids = [row.get("record_id", "") for row in prices]
    if not all(price_ids) or len(price_ids) != len(set(price_ids)):
        raise ValueError("prices.csv has missing or duplicate record_id")
    if set(details) != set(price_ids):
        raise ValueError("offer-details.csv record_ids do not match prices.csv")
    groups: dict[str, list[dict[str, str]]] = {}
    unresolved: set[tuple[str, str]] = set()
    for price in prices:
        seller = price.get("platform", "").strip()
        seller_id = price.get("model_id", "").strip()
        record_id = price.get("record_id", "")
        if not seller or not seller_id or not record_id:
            raise ValueError("prices.csv has a row without platform, model_id or record_id")
        detail = details[record_id]
        if detail.get("seller_model_id") != seller_id:
            raise ValueError(f"offer-details.csv seller_model_id mismatch for {record_id}")
        if detail.get("observed_at") not in evidence_times.get((seller, price.get("source_url", "")), set()):
            raise ValueError(f"offer-details.csv observed_at does not match fetch evidence for {record_id}")
        if seller in OFFICIAL_SELLERS and price.get("platform_type") == "official":
            canonical = seller_id
            creator = detail.get("model_creator") or OFFICIAL_CREATORS[seller]
            if creator != OFFICIAL_CREATORS[seller]:
                raise ValueError(f"Unexpected official model creator for {record_id}")
            confidence = "exact"
        else:
            alias = aliases.get((seller.casefold(), seller_id))
            if alias is None:
                unresolved.add((seller, seller_id))
                continue
            canonical = alias.canonical_model_id
            creator = alias.model_creator
            confidence = alias.confidence
        obs = {
            "snapshot_date": price.get("last_checked", ""),
            "canonical_model_id": canonical,
            "model_name": price.get("model_name", "") or seller_id,
            "model_creator": creator,
            "seller": seller,
            "seller_type": price.get("platform_type", ""),
            "seller_model_id": detail.get("seller_model_id") or seller_id,
            "currency": price.get("currency", ""),
            "input_per_1m": price.get("input_per_1m", ""),
            "output_per_1m": price.get("output_per_1m", ""),
            "cache_read_per_1m": price.get("cache_read_per_1m", ""),
            "cache_write_per_1m": price.get("cache_write_per_1m", ""),
            "cache_write_5m_per_1m": detail.get("cache_write_5m_per_1m", ""),
            "cache_write_1h_per_1m": detail.get("cache_write_1h_per_1m", ""),
            "cache_storage_per_1m_hour": detail.get("cache_storage_per_1m_hour", ""),
            "context_tier": price.get("context_tier", ""),
            "context_limit_tokens": price.get("context_limit_tokens", ""),
            "context_threshold_tokens": detail.get("context_threshold_tokens", ""),
            "service_tier": detail.get("service_tier", ""),
            "time_band": detail.get("time_band", ""),
            "pricing_variant": price.get("pricing_variant", ""),
            "promotion_status": detail.get("promotion_status", ""),
            "effective_start": detail.get("effective_start", ""),
            "effective_end": detail.get("effective_end", ""),
            "charge_type": detail.get("charge_type", "token"),
            "modality": detail.get("modality", "text"),
            "verification_status": price.get("verification_status", ""),
            "source_url": price.get("source_url", ""),
            "observed_at": detail.get("observed_at") or price.get("last_checked", ""),
            "has_official_reference": "",
            "official_seller": "",
            "match_status": "matched",
            "match_confidence": confidence,
            "record_id": record_id,
            "market_scope": price.get("market_scope", ""),
            "brazil_relevance": price.get("brazil_relevance", ""),
        }
        groups.setdefault(canonical, []).append(obs)

    observations: list[dict[str, str]] = []
    summaries: list[dict[str, str]] = []
    for canonical, offers in sorted(groups.items()):
        sellers = {r["seller"] for r in offers}
        if len(sellers) < 2:
            continue
        official = sorted(s for s in sellers if s in OFFICIAL_SELLERS and any(
            r["seller"] == s and r["seller_type"] == "official" for r in offers))
        named = next((r for r in offers if r["seller"] in official), offers[0])
        for row in offers:
            row["has_official_reference"] = "true" if official else "false"
            row["official_seller"] = ";".join(official)
        observations.extend(sorted(offers, key=lambda r: (r["seller"], r["pricing_variant"], r["record_id"])))
        summaries.append({
            "canonical_model_id": canonical,
            "model_name": named["model_name"],
            "model_creator": named["model_creator"],
            "seller_count": str(len(sellers)),
            "numeric_offer_count": str(sum(any(r[c] != "" for c in (
                "input_per_1m", "output_per_1m", "cache_read_per_1m", "cache_write_per_1m"))
                for r in offers)),
            "official_reference_count": str(len(official)),
            "gateway_count": str(len({r["seller"] for r in offers if r["seller_type"] == "gateway"})),
            "currencies": ";".join(sorted({r["currency"] for r in offers if r["currency"]})),
            "has_official_reference": "true" if official else "false",
            "has_openrouter": "true" if "OpenRouter" in sellers else "false",
            "has_brazil_seller": "true" if any(r["market_scope"].casefold() == "brazil"
                                                for r in offers) else "false",
            "has_mandapi": "true" if "MandAPI" in sellers else "false",
        })
    return MatchedSample(observations, summaries, sorted(unresolved))


def write_matched_sample(out_dir: str | Path, sample: MatchedSample) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for filename, columns, rows in (
        ("matched-observations.csv", OBSERVATION_COLUMNS, sample.observations),
        ("matched-summary.csv", SUMMARY_COLUMNS, sample.summary),
    ):
        with (out / filename).open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    with (out / "unresolved-aliases.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=UNRESOLVED_COLUMNS)
        writer.writeheader()
        writer.writerows({
            "seller": seller, "seller_model_id": model_id,
            "canonical_model_id": "", "match_status": "unresolved",
        } for seller, model_id in sample.unresolved)
