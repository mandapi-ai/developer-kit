"""Deterministic parsers for the public Gemini and DeepSeek pricing pages.

These adapters deliberately accept a narrow, auditable subset of each page:
paid text-token Gemini offers and DeepSeek's published per-million-token table.
Unrelated free quotas, image/request charges, and future prices are not retail
text-token observations. A page whose expected structure disappears is an error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from bs4 import BeautifulSoup, Tag

from .base import Adapter
from ..fetch import FetchResult
from ..models import PriceRecord, SourceSpec


_GOOGLE_TIERS = {"standard", "batch", "flex", "priority"}
_EXCLUDED_GOOGLE_PRODUCTS = (
    "live", "audio", "translate", "transcribe", "image", "tts", "omni",
    "embedding", "robotics", "veo", "lyria", "gemma",
)
# Accept comma-grouped USD amounts, while rejecting a malformed group instead of
# accidentally reading its leading digit as the whole price. A comma followed
# by whitespace remains a valid separator before a rate's description.
_MONEY_LINE = re.compile(r"^(?:US)?\$\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?![\d.]|,\d)(.*)$", re.I)
_ENGLISH_DATE = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
_CONTEXT = re.compile(r"prompts?\s*(<=|≤|>|≥)\s*(\d+(?:\.\d+)?)\s*([kKmM])?\s*tokens?", re.I)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _tier_slug(tier: str) -> str:
    if tier.startswith("<="):
        return "lte" + tier[2:]
    if tier.startswith(">"):
        return "gt" + tier[1:]
    return _slug(tier) or "base"


def _observed_date(fetched: FetchResult) -> date:
    return date.fromisoformat(fetched.evidence.fetched_at[:10])


def _text_lines(cell: Tag) -> list[str]:
    return [line.strip() for line in cell.get_text("\n", strip=True).splitlines() if line.strip()]


@dataclass(frozen=True)
class _Rate:
    amount: Decimal
    context_tier: str = ""
    context_threshold_tokens: int | None = None
    effective_start: str = ""
    effective_end: str = ""


def _line_dates(line: str) -> tuple[str, str]:
    start_match = re.search(rf"\bstarting\s+({_ENGLISH_DATE})", line, re.I)
    end_match = re.search(rf"\bthrough\s+({_ENGLISH_DATE})", line, re.I)

    def to_iso(match: re.Match[str] | None) -> str:
        return datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat() if match else ""

    return to_iso(start_match), to_iso(end_match)


def _context_for(line: str) -> tuple[str, int | None]:
    match = _CONTEXT.search(line)
    if not match:
        return "", None
    amount = Decimal(match.group(2)) * {"": 1, "k": 1_000, "m": 1_000_000}[match.group(3).lower() if match.group(3) else ""]
    threshold = int(amount)
    operator = "<=" if match.group(1) in {"<=", "≤"} else ">"
    return f"{operator}{threshold}", threshold


def _parse_google_rates(cell: Tag, *, observed: date, storage: bool = False) -> list[_Rate]:
    rates: list[_Rate] = []
    for line in _text_lines(cell):
        match = _MONEY_LINE.match(line)
        if not match:
            if re.match(r"^(?:US)?\$", line, re.I):
                raise ValueError(f"Gemini price has unsupported USD format: {line!r}")
            continue
        detail = match.group(2).strip()
        is_storage = bool(re.search(r"storage price|tokens\s+per\s+hour", detail, re.I))
        if is_storage != storage:
            continue
        # An audio-only rate, per-image charge or per-request charge is not a
        # text-token price, even when it appears under a per-token table header.
        if re.search(r"\bper\s+(?:image|request|second)\b", detail, re.I):
            continue
        qualifier = re.search(r"\(([^)]*)\)", detail)
        if qualifier and re.search(r"\baudio\b", qualifier.group(1), re.I) and not re.search(r"\btext\b", qualifier.group(1), re.I) and not is_storage:
            continue
        start, end = _line_dates(detail)
        if start and observed < date.fromisoformat(start):
            continue
        if end and observed > date.fromisoformat(end):
            continue
        tier, limit = _context_for(detail)
        rates.append(_Rate(Decimal(match.group(1).replace(",", "")), tier, limit, start, end))
    return rates


def _unique_rate(rates: list[_Rate], tier: str, label: str) -> _Rate | None:
    candidates = [rate for rate in rates if rate.context_tier == tier]
    if not candidates and tier:
        candidates = [rate for rate in rates if not rate.context_tier]
    if not candidates:
        return None
    if len(set(candidates)) != 1:
        raise ValueError(f"Conflicting active Gemini {label} rates for context tier {tier!r}")
    return candidates[0]


def _price_table_rows(table: Tag) -> dict[str, tuple[Tag, Tag]]:
    header = table.find("tr")
    headings = [c.get_text(" ", strip=True) for c in header.find_all(["th", "td"], recursive=False)] if header else []
    if len(headings) != 3 or not re.search(r"Paid Tier,\s*per 1M tokens in USD", headings[2], re.I):
        raise ValueError("Gemini pricing table no longer has an explicit USD per-1M paid column")
    fields: dict[str, tuple[Tag, Tag]] = {}
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all(["th", "td"], recursive=False)
        if len(cells) != 3:
            continue
        label = cells[0].get_text(" ", strip=True).lower()
        if label.startswith("input price"):
            key = "input"
        elif label.startswith("output price"):
            key = "output"
        elif label.startswith("context caching price"):
            key = "cache"
        else:
            continue
        if key in fields:
            raise ValueError(f"Duplicate Gemini {key} row")
        fields[key] = (cells[1], cells[2])
    if "input" not in fields or "output" not in fields:
        raise ValueError("Gemini paid text-token table has no input/output rows")
    return fields


class GoogleAiStudioAdapter(Adapter):
    """Parse current paid Gemini text-token rates from the official HTML table."""

    def parse(self, source: SourceSpec, fetched: FetchResult) -> list[PriceRecord]:
        if not fetched.text:
            raise ValueError("Empty Gemini pricing page")
        soup = BeautifulSoup(fetched.text, "html.parser")
        observed = _observed_date(fetched)
        records: list[PriceRecord] = []
        seen: set[tuple[str, str, str]] = set()
        model_ids: list[str] = []
        model_name = ""
        service = ""
        for node in soup.find_all(["h2", "h3", "table"]):
            if node.name == "h2":
                model_ids = []
                model_name = node.get_text(" ", strip=True)
                service = ""
                name_lower = model_name.lower()
                if not name_lower.startswith("gemini ") or any(part in name_lower for part in _EXCLUDED_GOOGLE_PRODUCTS):
                    continue
                id_node = node.find_next_sibling("em")
                if id_node:
                    model_ids = [code.get_text(" ", strip=True) for code in id_node.find_all("code")]
                if not model_ids or any(not re.fullmatch(r"gemini-[a-z0-9][a-z0-9.-]*", model_id) for model_id in model_ids):
                    model_ids = []
            elif node.name == "h3":
                label = node.get_text(" ", strip=True).lower()
                service = label if label in _GOOGLE_TIERS else ""
            elif model_ids and service and "pricing-table" in node.get("class", []):
                fields = _price_table_rows(node)
                paid = {key: _parse_google_rates(pair[1], observed=observed) for key, pair in fields.items()}
                storage = _parse_google_rates(fields["cache"][1], observed=observed, storage=True) if "cache" in fields else []
                if not paid["input"] or not paid["output"]:
                    continue  # unavailable, future-only, or non-text service
                tiers = {rate.context_tier for rates in paid.values() for rate in rates if rate.context_tier} or {""}
                for model_id in model_ids:
                    for tier in sorted(tiers):
                        prices = {key: _unique_rate(rates, tier, key) for key, rates in paid.items()}
                        if not prices["input"] or not prices["output"]:
                            continue
                        key = (model_id, service, tier)
                        if key in seen:
                            raise ValueError(f"Duplicate Gemini offer {key}")
                        seen.add(key)
                        storage_rate = _unique_rate(storage, tier, "storage")
                        used_rates = [rate for rate in prices.values() if rate is not None]
                        if storage_rate:
                            used_rates.append(storage_rate)
                        starts = [rate.effective_start for rate in used_rates if rate.effective_start]
                        ends = [rate.effective_end for rate in used_rates if rate.effective_end]
                        effective_start = max(starts, default="")
                        effective_end = min(ends, default="")
                        if effective_start and effective_end and effective_start > effective_end:
                            raise ValueError(f"Incompatible Gemini effective dates for {key}")
                        records.append(PriceRecord(
                            record_id=f"{_slug(source.id)}-{_slug(model_id)}-{service}-{_tier_slug(tier)}",
                            model_id=model_id, seller_model_id=model_id,
                            canonical_model_id=model_id.lower(), model_name=model_name,
                            model_family="Gemini", model_provider="Google", model_creator="Google",
                            platform=source.platform, platform_type=source.platform_type,
                            source_type=source.source_type, currency="USD",
                            input_per_1m=prices["input"].amount,
                            output_per_1m=prices["output"].amount,
                            cache_read_per_1m=prices["cache"].amount if prices.get("cache") else None,
                            cache_storage_per_1m_hour=storage_rate.amount if storage_rate else None,
                            context_tier=tier,
                            context_threshold_tokens=next((rate.context_threshold_tokens for rate in used_rates if rate.context_threshold_tokens), None),
                            service_tier=service, pricing_variant=f"paid_{service}",
                            promotion_status="time_limited" if effective_end else "",
                            effective_start=effective_start, effective_end=effective_end,
                            charge_type="token", modality="text", price_scope="retail_price",
                            market_scope=source.market_scope, brazil_relevance=source.brazil_relevance,
                            openai_compatible=source.openai_compatible,
                            verification_status="public_source", observed_at=fetched.evidence.fetched_at,
                            last_checked=observed.isoformat(), source_url=fetched.evidence.url or source.pricing_url,
                            notes="Paid text-token rate; cache storage, if present, is USD per 1M cached tokens per hour. Free-tier quotas and non-text charges are excluded.",
                        ))
        if not records:
            raise ValueError("No supported paid Gemini text-token prices on official page")
        return records


def _deepseek_price(cell: Tag) -> Decimal | None:
    value = cell.get_text(" ", strip=True)
    if value.lower() in {"", "-", "n/a", "not available"}:
        return None
    match = re.fullmatch(r"(?:US)?\$\s*(\d+(?:\.\d+)?)", value, re.I)
    if not match:
        raise ValueError(f"DeepSeek price has unsupported currency or format: {value!r}")
    return Decimal(match.group(1))


def _deepseek_context(table: Tag) -> int | None:
    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        if not cells or "CONTEXT LENGTH" not in cells[0].get_text(" ", strip=True).upper():
            continue
        value = cells[-1].get_text(" ", strip=True)
        match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([KMB])", value, re.I)
        if match:
            return int(Decimal(match.group(1)) * {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[match.group(2).upper()])
    return None


class DeepSeekAdapter(Adapter):
    """Parse cache hit/miss and peak/off-peak USD prices without blending them."""

    def parse(self, source: SourceSpec, fetched: FetchResult) -> list[PriceRecord]:
        if not fetched.text:
            raise ValueError("Empty DeepSeek pricing page")
        soup = BeautifulSoup(fetched.text, "html.parser")
        page_text = soup.get_text(" ", strip=True).replace("\u200b", "")
        peak_match = re.search(r"Peak hours are ([^.]+)\.", page_text, re.I)
        offpeak_match = re.search(r"All other hours are off-peak, ([^.]+)\.", page_text, re.I)
        if not peak_match or not offpeak_match:
            raise ValueError("DeepSeek peak/off-peak schedule is missing")
        table = next((item for item in soup.find_all("table") if "MODEL" in item.get_text(" ", strip=True).upper() and "CACHE HIT" in item.get_text(" ", strip=True).upper()), None)
        if table is None:
            raise ValueError("DeepSeek model pricing table is missing")
        rows = table.find_all("tr")
        if not rows:
            raise ValueError("DeepSeek model pricing table has no rows")
        header = rows[0].find_all(["th", "td"], recursive=False)
        models = [re.sub(r"\s*\(\d+\)$", "", cell.get_text(" ", strip=True)) for cell in header[1:]]
        if not models or len(set(models)) != len(models) or any(not re.fullmatch(r"deepseek-[a-z0-9][a-z0-9-]*", model) for model in models):
            raise ValueError("DeepSeek pricing table has invalid or duplicate model IDs")
        versions: dict[str, str] = {}
        context_limit = _deepseek_context(table)
        prices: dict[tuple[str, str], dict[str, Decimal | None]] = {}
        current_charge = ""
        found_rows = 0
        for tr in rows[1:]:
            cells = tr.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            first = cells[0].get_text(" ", strip=True).upper()
            if "MODEL VERSION" in first:
                if len(cells) < len(models) + 1:
                    raise ValueError("DeepSeek model versions are incomplete")
                versions = dict(zip(models, [cell.get_text(" ", strip=True) for cell in cells[-len(models):]]))
                continue
            for cell in cells[:-len(models)]:
                label = cell.get_text(" ", strip=True).upper()
                if "INPUT TOKENS" in label and "CACHE HIT" in label:
                    current_charge = "cache_hit"
                elif "INPUT TOKENS" in label and "CACHE MISS" in label:
                    current_charge = "cache_miss"
                elif "OUTPUT TOKENS" in label:
                    current_charge = "output"
            if not current_charge or len(cells) < len(models) + 1:
                continue
            time_cell = cells[-len(models) - 1].get_text(" ", strip=True).upper().replace("-", "_")
            if time_cell not in {"PEAK", "OFF_PEAK"}:
                continue
            found_rows += 1
            for model, cell in zip(models, cells[-len(models):]):
                key = (model, time_cell.lower())
                value = _deepseek_price(cell)
                charges = prices.setdefault(key, {})
                if current_charge in charges and charges[current_charge] != value:
                    raise ValueError(f"Conflicting DeepSeek {current_charge} offer for {key}")
                charges[current_charge] = value
        if not found_rows or not versions:
            raise ValueError("DeepSeek pricing rows or model versions are missing")
        required_charges = {"cache_hit", "cache_miss", "output"}
        for model in models:
            for period in ("peak", "off_peak"):
                key = (model, period)
                charges = prices.get(key, {})
                missing = required_charges - charges.keys()
                if missing:
                    raise ValueError(f"Incomplete DeepSeek pricing rows for {key}: missing {', '.join(sorted(missing))}")
                if charges["cache_miss"] is None or charges["output"] is None:
                    raise ValueError(f"DeepSeek input/output price is unavailable for {key}")
        observed = _observed_date(fetched)
        results: list[PriceRecord] = []
        for (model, period), charges in sorted(prices.items()):
            schedule = ("Peak hours are " + peak_match.group(1) if period == "peak" else "All other hours are off-peak, " + offpeak_match.group(1))
            results.append(PriceRecord(
                record_id=f"{_slug(source.id)}-{_slug(model)}-{period}",
                model_id=model, seller_model_id=model, canonical_model_id=model.lower(),
                model_name=versions[model] or model, model_family="DeepSeek",
                model_provider="DeepSeek", model_creator="DeepSeek",
                platform=source.platform, platform_type=source.platform_type,
                source_type=source.source_type, currency="USD",
                input_per_1m=charges.get("cache_miss"),
                cache_read_per_1m=charges.get("cache_hit"),
                output_per_1m=charges.get("output"),
                context_limit_tokens=context_limit, pricing_variant=f"paid_{period}",
                service_tier="standard", time_band=schedule,
                charge_type="token", modality="text", price_scope="retail_price",
                market_scope=source.market_scope, brazil_relevance=source.brazil_relevance,
                openai_compatible=source.openai_compatible,
                verification_status="public_source", observed_at=fetched.evidence.fetched_at,
                last_checked=observed.isoformat(), source_url=fetched.evidence.url or source.pricing_url,
                notes="Input is the published cache-miss price; cache read is cache-hit. " + schedule + ".",
            ))
        if not results:
            raise ValueError("No supported DeepSeek token prices on official page")
        return results
