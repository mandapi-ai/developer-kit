from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import Adapter
from ..fetch import FetchResult
from ..models import PriceRecord, SourceSpec
from ..normalize import (
    canonicalize_model_id,
    detect_currency,
    infer_model_family,
    infer_model_provider,
    parse_decimal_price,
)


MODEL_HEADERS = {"model", "modelo", "model id", "modelo / endpoint", "modelo/endpoint", "name", "nome"}
INPUT_HEADERS = {"base input", "input", "entrada", "prompt", "input price", "preço entrada", "preco entrada"}
OUTPUT_HEADERS = {"output", "saída", "saida", "completion", "output price", "preço saída", "preco saida"}
CACHE_READ_HEADERS = {"cache read", "cached input", "cache", "cache hit", "leitura cache"}
CACHE_WRITE_HEADERS = {"cache write", "cache creation", "cache create", "gravação cache", "gravacao cache"}


def _norm_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _find_index(headers: list[str], candidates: set[str]) -> int | None:
    for idx, header in enumerate(headers):
        h = _norm_header(header)
        if h in candidates:
            return idx
        if any(re.match(r"^" + re.escape(candidate) + r"(?:\s*(?:price|/|\(|\[|\$).*)?$", h) for candidate in candidates):
            return idx
    return None


class GenericHtmlTableAdapter(Adapter):
    """Conservative table parser. Output is always needs_review."""

    def parse(self, source: SourceSpec, fetched: FetchResult) -> list[PriceRecord]:
        if not fetched.text or source.unit != "per_1m_tokens":
            return []

        soup = BeautifulSoup(fetched.text, "html.parser")
        records: list[PriceRecord] = []
        seen = {}

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            header_cells = rows[0].find_all(["th", "td"])
            headers = [_norm_header(c.get_text(" ", strip=True)) for c in header_cells]
            model_i = _find_index(headers, MODEL_HEADERS)
            input_i = _find_index(headers, INPUT_HEADERS)
            output_i = _find_index(headers, OUTPUT_HEADERS)
            cache_r_i = _find_index(headers, CACHE_READ_HEADERS)
            cache_w_i = _find_index(headers, CACHE_WRITE_HEADERS)
            unit_i = _find_index(headers, {"billing unit", "unit", "unidade"})
            if model_i is None or (input_i is None and output_i is None):
                continue

            for row in rows[1:]:
                cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
                if model_i >= len(cells):
                    continue
                if unit_i is not None and (unit_i >= len(cells) or not re.search(r"(?:1m|million|milhão).*tokens", cells[unit_i], re.I)):
                    continue
                model_cell = row.find_all(["th", "td"])[model_i]
                code = model_cell.find("code")
                model_name = cells[model_i].strip()
                if not model_name:
                    continue

                def cell(i: int | None) -> str:
                    return cells[i] if i is not None and i < len(cells) else ""

                input_text, output_text = cell(input_i), cell(output_i)
                price_texts = [input_text, output_text, cell(cache_r_i), cell(cache_w_i)]
                # Explicit cell units override registry defaults; unsupported scales are skipped.
                if any(re.search(r"per\s+token\b|/\s*(?:token\b|1k|1000)|per\s+(?:image|second|request)", text, re.I) for text in price_texts + headers):
                    continue
                if any(len(set(re.findall(r"R\$|US\$|(?<![A-Za-z])\$|BRL|USD|CNY|RMB|¥", text, re.I))) > 1 for text in price_texts):
                    continue
                currencies = {detect_currency(text, source.default_currency) for text in price_texts if parse_decimal_price(text) is not None}
                if len(currencies) > 1:
                    continue
                input_price = parse_decimal_price(input_text)
                output_price = parse_decimal_price(output_text)
                if input_price is None and output_price is None:
                    continue

                currency = detect_currency(" ".join([input_text, output_text, cell(cache_r_i), cell(cache_w_i)]), source.default_currency)
                model_id = code.get_text(strip=True) if code else model_name
                key = (source.id, model_id, currency)
                if key in seen:
                    if seen[key] != cells:
                        raise ValueError(f"Ambiguous duplicate HTML offer {key}; use a provider-specific tier adapter")
                    continue
                seen[key] = cells

                records.append(
                    PriceRecord(
                        record_id=f"{_slug(source.id)}-{_slug(model_id)}",
                        model_id=model_id,
                        canonical_model_id=canonicalize_model_id(model_id),
                        model_name=model_name,
                        model_family=infer_model_family(model_id, model_name),
                        model_provider=infer_model_provider(model_id, model_name),
                        platform=source.platform,
                        platform_type=source.platform_type,
                        source_type=source.source_type,
                        currency=currency,
                        input_per_1m=input_price,
                        output_per_1m=output_price,
                        cache_read_per_1m=parse_decimal_price(cell(cache_r_i)),
                        cache_write_per_1m=parse_decimal_price(cell(cache_w_i)),
                        pricing_variant="table_candidate",
                        price_scope="retail_price",
                        market_scope=source.market_scope,
                        brazil_relevance=source.brazil_relevance,
                        openai_compatible=source.openai_compatible,
                        verification_status="needs_review",
                        source_url=fetched.evidence.url or source.pricing_url,
                        notes="Candidate parsed from a public HTML table. Verify table semantics and units before research publication.",
                    )
                )
        return records
