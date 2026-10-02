"""Deterministic extraction of first-party OpenAI and Anthropic token rates.

The adapters only consume the fetched public document.  They intentionally do
not fetch linked model pages, infer undisclosed rates, or convert currencies.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from .base import Adapter
from ..models import PriceRecord


_DOLLAR = re.compile(r"^\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)$")
_ANTHROPIC_RATE = re.compile(r"^\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*/\s*MTok(?:\s*\d+)?$")
_OPENAI_MODEL = re.compile(r"^[a-z][a-z0-9._-]*$")
_CONTEXT_ANNOTATION = re.compile(r"^([a-z][a-z0-9._-]*)\s*\(<\s*(\d+)K\s+context length\)$", re.I)
_ANTHROPIC_MODEL_LINK = re.compile(r"^/docs/en/models/([a-z0-9-]+)/overview/?$")
_OPENAI_TIERS = ("standard", "batch", "flex", "fast", "ultrafast")
_OPENAI_COLUMNS = [
    "Model", "Short context input", "Short context cached input",
    "Short context cache writes", "Short context output",
    "Long context input", "Long context cached input",
    "Long context cache writes", "Long context output",
]
_OPENAI_HTML_COLUMNS = [
    "Model", "Input", "Cached input", "Cache writes", "Output",
    "Input", "Cached input", "Cache writes", "Output",
]


def _rate(value: str, *, mtok: bool = False) -> Decimal | None:
    value = value.strip()
    if value in {"-", "—"}:
        return None
    match = (_ANTHROPIC_RATE if mtok else _DOLLAR).fullmatch(value)
    if match is None:
        raise ValueError(f"Unexpected official price cell: {value!r}")
    try:
        amount = Decimal(match.group(1).replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid official price cell: {value!r}") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"Invalid official price cell: {value!r}")
    return amount


def _record_id(source_id: str, model_id: str, service: str, context: str) -> str:
    key = "\x1f".join((source_id, model_id, service, context))
    return f"{source_id}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:20]}"


def _insert_unique(out: dict[tuple[str, str, str], PriceRecord], row: PriceRecord) -> None:
    key = (row.model_id, row.service_tier, row.context_tier)
    previous = out.get(key)
    if previous is None:
        out[key] = row
        return
    fields = ("input_per_1m", "output_per_1m", "cache_read_per_1m", "cache_write_per_1m",
              "cache_write_5m_per_1m", "cache_write_1h_per_1m", "promotion_status")
    if any(getattr(previous, field) != getattr(row, field) for field in fields):
        raise ValueError(f"Conflicting duplicate official offer: {key!r}")


def _openai_model(label: str) -> tuple[str, int | None]:
    label = label.strip()
    annotated = _CONTEXT_ANNOTATION.fullmatch(label)
    if annotated:
        return annotated.group(1), int(annotated.group(2)) * 1000
    if _OPENAI_MODEL.fullmatch(label):
        return label, None
    raise ValueError(f"Unexpected OpenAI model label: {label!r}")


def _openai_prices(cells: list[str]) -> list[tuple[str, dict[str, Decimal | None]]]:
    if len(cells) != 9:
        raise ValueError(f"OpenAI pricing row has {len(cells)} cells, expected 9")
    result = []
    for context, offset in (("short_context", 1), ("long_context", 5)):
        values = {
            "input_per_1m": _rate(cells[offset]),
            "cache_read_per_1m": _rate(cells[offset + 1]),
            "cache_write_per_1m": _rate(cells[offset + 2]),
            "output_per_1m": _rate(cells[offset + 3]),
        }
        if any(value is not None for value in values.values()):
            result.append((context, values))
    return result


def _openai_markdown_tables(document: str) -> list[tuple[str, list[list[str]]]]:
    lines = document.splitlines()
    tables = []
    for tier in _OPENAI_TIERS:
        heading = f"### {tier.capitalize()} pricing data"
        positions = [i for i, line in enumerate(lines) if line.strip() == heading]
        if not positions:
            if tier == "standard":
                raise ValueError("OpenAI standard pricing section is missing")
            continue
        if len(positions) != 1:
            raise ValueError(f"Duplicate OpenAI {tier} pricing sections")
        i = positions[0] + 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i + 2 >= len(lines):
            raise ValueError(f"OpenAI {tier} pricing table is incomplete")
        header = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
        if header != _OPENAI_COLUMNS or not re.fullmatch(r"[\s|:-]+", lines[i + 1]):
            raise ValueError(f"OpenAI {tier} pricing header changed")
        i += 2
        rows = []
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            rows.append([cell.strip() for cell in lines[i].strip().strip("|").split("|")])
            i += 1
        if not rows:
            raise ValueError(f"OpenAI {tier} pricing table is empty")
        tables.append((tier, rows))
    return tables


def _openai_html_tables(document: str) -> list[tuple[str, list[list[str]]]]:
    soup = BeautifulSoup(document, "html.parser")
    root = soup.select_one("#content-switcher-latest-pricing")
    if root is None:
        raise ValueError("OpenAI pricing switcher is missing")
    tables = []
    for pane in root.select(".content-switcher-panes > div[data-value]"):
        tier = pane.get("data-value")
        if tier not in _OPENAI_TIERS:
            continue
        table = pane.find("table")
        if table is None:
            raise ValueError(f"OpenAI {tier} pricing table is missing")
        rows = table.find_all("tr")
        if len(rows) < 3:
            raise ValueError(f"OpenAI {tier} pricing table is incomplete")
        group = [cell.get_text(" ", strip=True) for cell in rows[0].find_all(["th", "td"], recursive=False)]
        header = [cell.get_text(" ", strip=True) for cell in rows[1].find_all(["th", "td"], recursive=False)]
        if group != ["", "Short context", "Long context"] or header != _OPENAI_HTML_COLUMNS:
            raise ValueError(f"OpenAI {tier} pricing header changed")
        data = [[cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"], recursive=False)]
                for row in rows[2:]]
        tables.append((tier, data))
    if not any(tier == "standard" for tier, _ in tables):
        raise ValueError("OpenAI standard pricing section is missing")
    return tables


class OpenAIOfficialAdapter(Adapter):
    """Parse official full Markdown, with deterministic HTML table fallback."""

    def parse(self, source, fetched):
        if source.default_currency != "USD":
            raise ValueError("OpenAI official source must preserve USD")
        document = fetched.text
        tables = (_openai_markdown_tables(document) if document.lstrip().startswith("#")
                  else _openai_html_tables(document))
        promotion = re.search(
            r"GPT-5\.6 Sol[’']s promotional pricing is available at least through\s+"
            r"([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", document,
        )
        out: dict[tuple[str, str, str], PriceRecord] = {}
        for tier, rows in tables:
            for cells in rows:
                if len(cells) != 9:
                    raise ValueError(f"OpenAI {tier} pricing row has {len(cells)} cells")
                model_id, threshold = _openai_model(cells[0])
                for context, values in _openai_prices(cells):
                    notes = ["Official per-1M-token rate."]
                    if threshold is not None:
                        notes.append(f"Page label: {cells[0]}; context threshold {threshold} tokens.")
                    promoted = bool(promotion and model_id == "gpt-5.6-sol")
                    if promoted:
                        notes.append(f"Promotional pricing available at least through {promotion.group(1)}; end date not stated.")
                    row = PriceRecord(
                        record_id=_record_id(source.id, model_id, tier, context),
                        model_id=model_id, seller_model_id=model_id,
                        canonical_model_id=model_id, model_name=model_id,
                        model_family="GPT", model_provider="OpenAI", model_creator="OpenAI",
                        platform=source.platform, platform_type=source.platform_type,
                        source_type=source.source_type, currency="USD", service_tier=tier,
                        context_tier=context, context_threshold_tokens=threshold,
                        pricing_variant=f"{tier}:{context}",
                        market_scope=source.market_scope, brazil_relevance=source.brazil_relevance,
                        openai_compatible=source.openai_compatible,
                        verification_status="public_source", source_url=fetched.evidence.url or source.pricing_url,
                        observed_at=fetched.evidence.fetched_at,
                        last_checked=fetched.evidence.fetched_at[:10],
                        promotion_status="promotion" if promoted else "",
                        notes=" ".join(notes), **values,
                    )
                    _insert_unique(out, row)
        if not out:
            raise ValueError("OpenAI official pricing contains no supported token rates")
        return list(out.values())


def _anthropic_model(cell) -> tuple[str, str] | None:
    link = cell.find("a", href=True)
    if link is None:
        # The legacy display-only rows have no model ID on this pricing page.
        return None
    match = _ANTHROPIC_MODEL_LINK.fullmatch(link["href"])
    if match is None:
        return None
    name = link.get_text(" ", strip=True)
    if not re.fullmatch(r"Claude\s+[A-Za-z]+\s+\d+(?:\.\d+)?", name):
        raise ValueError(f"Unexpected linked Anthropic model name: {name!r}")
    return f"claude-{match.group(1)}", name


def _anthropic_table(soup, heading_id: str, expected: list[str]):
    heading = soup.find(id=heading_id)
    if heading is None:
        return None
    table = heading.find_next("table")
    if table is None:
        raise ValueError(f"Anthropic {heading_id} pricing table is missing")
    rows = table.find_all("tr")
    if len(rows) < 2:
        raise ValueError(f"Anthropic {heading_id} pricing table is incomplete")
    headers = [[cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"], recursive=False)]
               for row in rows[:2]]
    if headers[0] == expected:
        return rows[1:]
    if headers[1] == expected:
        return rows[2:]
    raise ValueError(f"Anthropic {heading_id} pricing header changed: {headers!r}")


class AnthropicOfficialAdapter(Adapter):
    """Parse public first-party Claude standard, batch, and fast token tables."""

    def parse(self, source, fetched):
        if source.default_currency != "USD":
            raise ValueError("Anthropic official source must preserve USD")
        soup = BeautifulSoup(fetched.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        if "All prices are in USD" not in text:
            raise ValueError("Anthropic official USD declaration is missing")
        standard = _anthropic_table(
            soup, "model-pricing",
            ["Name", "Input", "Output", "5m writes", "1h writes", "Hits and refreshes"],
        )
        if standard is None:
            raise ValueError("Anthropic model pricing section is missing")
        out: dict[tuple[str, str, str], PriceRecord] = {}
        names: dict[str, str] = {}

        def build(model_id: str, name: str, tier: str, values: dict[str, Decimal | None], *, notes: str):
            row = PriceRecord(
                record_id=_record_id(source.id, model_id, tier, "standard"),
                model_id=model_id, seller_model_id=model_id,
                canonical_model_id=model_id, model_name=name,
                model_family="Claude", model_provider="Anthropic", model_creator="Anthropic",
                platform=source.platform, platform_type=source.platform_type,
                source_type=source.source_type, currency="USD", service_tier=tier,
                context_tier="standard", pricing_variant=tier,
                market_scope=source.market_scope, brazil_relevance=source.brazil_relevance,
                openai_compatible=source.openai_compatible,
                verification_status="public_source", source_url=fetched.evidence.url or source.pricing_url,
                observed_at=fetched.evidence.fetched_at, notes=notes, **values,
                last_checked=fetched.evidence.fetched_at[:10],
            )
            _insert_unique(out, row)

        for tr in standard:
            cells = tr.find_all(["td", "th"], recursive=False)
            if len(cells) == 1 and "Additional models" in cells[0].get_text(" ", strip=True):
                continue
            if not cells:
                continue
            if len(cells) != 6:
                raise ValueError(f"Anthropic model pricing row has {len(cells)} cells")
            identity = _anthropic_model(cells[0])
            if identity is None:
                continue
            model_id, name = identity
            rates = [_rate(cell.get_text(" ", strip=True), mtok=True) for cell in cells[1:]]
            if not any(value is not None for value in rates):
                continue
            names[name] = model_id
            build(model_id, name, "standard", dict(
                input_per_1m=rates[0], output_per_1m=rates[1],
                cache_write_per_1m=rates[2], cache_write_5m_per_1m=rates[2],
                cache_write_1h_per_1m=rates[3], cache_read_per_1m=rates[4],
            ), notes="Official Claude API per-MTok price. V2 cache_write_per_1m denotes the 5-minute write; the 1-hour write is in offer details." )

        batch = _anthropic_table(soup, "batch-processing", ["Name", "Input", "Output"])
        if batch is not None:
            for tr in batch:
                cells = tr.find_all(["td", "th"], recursive=False)
                if len(cells) == 1 and "Additional models" in cells[0].get_text(" ", strip=True):
                    continue
                if not cells:
                    continue
                if len(cells) != 3:
                    raise ValueError(f"Anthropic batch pricing row has {len(cells)} cells")
                identity = _anthropic_model(cells[0])
                if identity is None:
                    continue
                model_id, name = identity
                if names.get(name) != model_id:
                    raise ValueError(f"Anthropic batch identity differs from standard: {name!r}")
                input_price, output_price = [_rate(cell.get_text(" ", strip=True), mtok=True) for cell in cells[1:]]
                if input_price is None and output_price is None:
                    continue
                build(model_id, name, "batch", dict(input_per_1m=input_price, output_per_1m=output_price),
                      notes="Official Claude Batch API per-MTok token price; cache components are not supplied by this table.")

        fast = _anthropic_table(soup, "fast-mode-pricing", ["Model", "Input", "Output"])
        if fast is not None:
            for tr in fast:
                cells = tr.find_all(["td", "th"], recursive=False)
                if not cells:
                    continue
                if len(cells) != 3:
                    raise ValueError(f"Anthropic fast pricing row has {len(cells)} cells")
                names_in_cell = [part.strip() for part in cells[0].get_text(" ", strip=True).split(" / ")]
                input_price, output_price = [_rate(cell.get_text(" ", strip=True), mtok=True) for cell in cells[1:]]
                if input_price is None and output_price is None:
                    continue
                for name in names_in_cell:
                    model_id = names.get(name)
                    if model_id is None:
                        raise ValueError(f"Anthropic fast price names an unknown model: {name!r}")
                    build(model_id, name, "fast", dict(input_per_1m=input_price, output_per_1m=output_price),
                          notes="Official first-party Claude fast-mode per-MTok token price; cache components are not supplied by this table.")

        if not out:
            raise ValueError("Anthropic official pricing contains no linked model token rates")
        return list(out.values())
