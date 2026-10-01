from __future__ import annotations

import json
import hashlib
import re
from decimal import Decimal
from bs4 import BeautifulSoup
from .base import Adapter
from ..models import PriceRecord
from ..normalize import canonicalize_model_id, infer_model_family, infer_model_provider, parse_decimal_price


def record(source, fetched, model_id, name, currency, **prices):
    return PriceRecord(
        record_id=source.id + "-" + hashlib.sha256(json.dumps([model_id, currency, prices.get("context_tier", ""), prices.get("pricing_variant", "standard")]).encode()).hexdigest()[:20], model_id=model_id,
        canonical_model_id=canonicalize_model_id(model_id), model_name=name,
        model_family=infer_model_family(model_id, name), model_provider=infer_model_provider(model_id, name),
        platform=source.platform, platform_type=source.platform_type, source_type=source.source_type,
        currency=currency, market_scope=source.market_scope, brazil_relevance=source.brazil_relevance,
        openai_compatible=source.openai_compatible, verification_status="needs_review",
        source_url=fetched.evidence.url, notes="Provider-specific public HTML extraction; review before publication.", **prices,
    )


class RoteiaAdapter(Adapter):
    def parse(self, source, fetched):
        soup = BeautifulSoup(fetched.text, "html.parser")
        out = []
        for script in soup.find_all("script"):
            match = re.search(r"window\.__ROTEIA_PUBLIC_CATALOG__\s*=\s*", script.get_text())
            if not match:
                continue
            items, _ = json.JSONDecoder(parse_float=Decimal).raw_decode(script.get_text()[match.end():])
            if not isinstance(items, list):
                raise ValueError("Roteia catalog must be a list")
            for item in items:
                if item.get("pricingUnit") != "million_tokens" or not item.get("id"):
                    continue
                def price(key):
                    value = item.get(key)
                    if value is None:
                        return None
                    value = Decimal(str(value))
                    return value if value.is_finite() and value >= 0 else None
                values = dict(input_per_1m=price("priceInBrlPerM"), output_per_1m=price("priceOutBrlPerM"), cache_read_per_1m=price("cacheReadBrlPerM"), cache_write_per_1m=price("cacheWriteBrlPerM"))
                if not any(v is not None for v in values.values()):
                    continue
                base = record(source, fetched, item["id"], item.get("name") or item["id"], "BRL", **values)
                base.model_provider = item.get("providerName") or base.model_provider
                base.context_limit_tokens = item.get("contextWindowTokens")
                base.context_tier = "standard"
                out.append(base)
                tier = item.get("longContextPricingBrl")
                if isinstance(tier, dict) and isinstance(tier.get("thresholdTokens"), int):
                    # Cache prices for this tier are not declared; retain missing.
                    extended = record(source, fetched, item["id"], base.model_name, "BRL",
                        input_per_1m=parse_decimal_price(str(tier.get("priceInBrlPerM", ""))),
                        output_per_1m=parse_decimal_price(str(tier.get("priceOutBrlPerM", ""))),
                        context_tier=f">{tier['thresholdTokens']}")
                    if extended.input_per_1m is not None or extended.output_per_1m is not None:
                        base.context_tier = f"<={tier['thresholdTokens']}"
                        extended.model_provider = base.model_provider
                        extended.context_limit_tokens = base.context_limit_tokens
                        extended.record_id += "-long-context"
                        out.append(extended)
            return out
        return out


class RunAPIAdapter(Adapter):
    def parse(self, source, fetched):
        soup = BeautifulSoup(fetched.text, "html.parser")
        out = []
        seen = set()
        for row in soup.select("tr[data-pricing-table-row]"):
            cells = row.find_all("td", recursive=False)
            if len(cells) != 7:
                continue
            header = row.find_previous("tr")
            while header is not None and not header.find("th", attrs={"scope": "col"}):
                header = header.find_previous("tr")
            if header is None or "RunAPI in/M" not in header.get_text():
                continue
            if any("/ 1M tokens" not in cells[i].get_text() for i in (2, 3)):
                continue
            model_id = " ".join(str(x).strip() for x in cells[0].find_all(string=True, recursive=False)).strip()
            variant = cells[0].find("span")
            variant = variant.get_text(strip=True) if variant else "standard"
            key = (model_id, variant)
            if not model_id or key in seen:
                continue
            detail = row.find_next_sibling("tr")
            tiers = {}
            component_map = {"Input": "input_per_1m", "Output": "output_per_1m", "Cached input": "cache_read_per_1m", "Cache write": "cache_write_per_1m"}
            if detail is not None and detail.has_attr("data-pricing-table-details"):
                for block in detail.select("dl > div"):
                    dt, dd = block.find("dt"), block.find("dd")
                    if dt is None or dd is None or "/ 1M tokens" not in dd.get_text():
                        continue
                    label = dt.get_text(" ", strip=True)
                    if " · " not in label:
                        continue
                    tier, component = label.rsplit(" · ", 1)
                    if not tier.startswith("Prompt ") or component not in component_map:
                        continue
                    tiers.setdefault(tier, {})[component_map[component]] = parse_decimal_price(dd.get_text())
            quotes = list(tiers.items()) if tiers else [("standard", dict(
                input_per_1m=parse_decimal_price(cells[2].get_text()),
                output_per_1m=parse_decimal_price(cells[3].get_text())))]
            for tier, values in quotes:
                if not any(value is not None for value in values.values()):
                    continue
                item = record(source, fetched, model_id, model_id, "USD",
                    pricing_variant=variant, context_tier=tier, **values)
                item.model_provider = cells[1].get_text(strip=True)
                item.record_id += "-" + re.sub(r"[^a-z0-9]+", "-", (variant + " " + tier).lower())
                out.append(item)
            if quotes:
                seen.add(key)
        return out


class KunavoAdapter(Adapter):
    """Join the public token-price and cache-price tables by displayed model name."""
    def parse(self, source, fetched):
        soup = BeautifulSoup(fetched.text, "html.parser")
        by_name = {}
        by_id = {}
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            headers = [c.get_text(" ", strip=True) for c in rows[0].find_all("th")] if rows else []
            if headers != ["Model", "Provider", "Input price", "Output price", "Billing unit", "vs Official"]:
                continue
            for row in rows[1:]:
                cells = row.find_all("td", recursive=False)
                if len(cells) != 6 or cells[4].get_text(strip=True) != "per 1M tokens":
                    continue
                link = cells[0].find("a", href=True)
                if link is None or not link["href"].startswith("/models/"):
                    continue
                model_id = link["href"].split("/models/", 1)[1]
                name = link.get_text(strip=True)
                item = record(source, fetched, model_id, name, "USD",
                    input_per_1m=parse_decimal_price(cells[2].get_text()),
                    output_per_1m=parse_decimal_price(cells[3].get_text()))
                item.model_provider = cells[1].get_text(strip=True)
                if item.input_per_1m is not None or item.output_per_1m is not None:
                    by_id[model_id] = item
                    by_name.setdefault(name, []).append(item)
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            headers = [c.get_text(" ", strip=True) for c in rows[0].find_all("th")] if rows else []
            if headers != ["Model", "Input", "Cache read", "Cache write", "Ratio"]:
                continue
            for row in rows[1:]:
                cells = row.find_all("td", recursive=False)
                if len(cells) != 5:
                    continue
                title = cells[0].find("div")
                matches = by_name.get(title.get_text(strip=True) if title else "", [])
                item = matches[0] if len(matches) == 1 else None
                if item is not None:
                    item.cache_read_per_1m = parse_decimal_price(cells[2].get_text())
                    item.cache_write_per_1m = parse_decimal_price(cells[3].get_text())
        return list(by_id.values())


class TokenRecargaAdapter(Adapter):
    def parse(self, source, fetched):
        soup = BeautifulSoup(fetched.text, "html.parser")
        out = []
        for card in soup.select('a[href^="/precos/"]'):
            code, title = card.find("code"), card.find("h3")
            if code is None or title is None:
                continue
            price = next((dd.get_text(" ", strip=True) for dd in card.find_all("dd") if "/ 1M tokens" in dd.get_text()), "")
            match = re.search(r"(R\$\s*[\d.,]+)\s+entrada.*?(R\$\s*[\d.,]+)\s+saída", price)
            if not match:
                continue
            item = record(source, fetched, code.get_text(strip=True), title.get_text(strip=True), "BRL",
                input_per_1m=parse_decimal_price(match[1]), output_per_1m=parse_decimal_price(match[2]))
            item.notes += " Tax excluded (sem impostos); account contract may differ."
            out.append(item)
        return out
