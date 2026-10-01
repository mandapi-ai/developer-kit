from __future__ import annotations

from decimal import Decimal, InvalidOperation
from .base import Adapter
from .provider_html import record


def decimal_rate(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number >= 0 else None
    except InvalidOperation:
        return None


def make_record(source, fetched, item, rates, tier, variant, mapping):
    values = {column: decimal_rate(rates.get(field)) for column, field in mapping.items()}
    if not any(value is not None for value in values.values()):
        return None
    model_id = item.get("id") or item.get("slug")
    if not isinstance(model_id, str) or not model_id:
        return None
    row = record(source, fetched, model_id, item.get("name") or item.get("display_name") or model_id,
        "USD", context_tier=tier, pricing_variant=variant, **values)
    row.record_id += f"-{variant}-{tier}"
    row.verification_status = "public_source"
    row.context_limit_tokens = item.get("context_length")
    return row


class OminiGateAdapter(Adapter):
    """Public catalog values are USD/1M (not OpenRouter's USD/token)."""
    def parse(self, source, fetched):
        payload = fetched.json_data
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError("OminiGate: expected data list")
        out = []
        mapping = {"input_per_1m": "prompt", "output_per_1m": "completion", "cache_read_per_1m": "input_cache_read", "cache_write_per_1m": "input_cache_write"}
        for item in payload["data"]:
            if not isinstance(item, dict) or "text" not in (item.get("output_modalities") or []):
                continue
            pricing = item.get("pricing")
            if not isinstance(pricing, dict):
                continue
            tiers = pricing.get("tiers") or []
            thresholds = sorted({t["threshold"] for t in tiers if isinstance(t, dict) and isinstance(t.get("threshold"), int) and t["threshold"] > 0})
            base_tier = f"<={thresholds[0]}" if thresholds else "standard"
            quotes = [(base_tier, pricing)]
            for t in tiers:
                if not isinstance(t, dict) or t.get("threshold") not in thresholds:
                    continue
                threshold = t["threshold"]
                later = [x for x in thresholds if x > threshold]
                tier = f"{threshold}<tokens<={later[0]}" if later else f">{threshold}"
                # Unspecified tier components remain missing; no inherited price assumptions.
                quotes.append((tier, t))
            for tier, rates in quotes:
                row = make_record(source, fetched, item, rates, tier, "catalog_list", mapping)
                if row is None:
                    continue
                row.notes = "Public OminiGate catalog API, USD per 1M tokens; catalog list rates, route discounts and non-token charges excluded. 1-hour cache-write variant excluded."
                out.append(row)
        return out


class APIMartAdapter(Adapter):
    """Export explicit base token rates, keeping group/member discounts separate."""
    def parse(self, source, fetched):
        payload = fetched.json_data
        models = payload.get("data", {}).get("models", {}) if isinstance(payload, dict) else {}
        if not isinstance(models, dict) or not isinstance(models.get("llm"), list):
            raise ValueError("APIMart: expected data.models.llm list")
        mapping = {"input_per_1m": "input", "output_per_1m": "output", "cache_read_per_1m": "cached_input", "cache_write_per_1m": "cache_write"}
        out = []
        for item in models["llm"]:
            if not isinstance(item, dict):
                continue
            pricing = item.get("pricing") or {}
            if pricing.get("unit") != "usd_per_million_tokens":
                continue
            tiers = pricing.get("tiers")
            if not tiers:
                tiers = item.get("token_pricing", {}).get("model", {}).get("tiers")
            if not tiers:
                tiers = [dict(pricing.get("rates") or {}, up_to_input_tokens=None)]
            lower = 0
            for rates in tiers:
                if not isinstance(rates, dict):
                    continue
                upper = rates.get("up_to_input_tokens")
                if upper is not None and (not isinstance(upper, int) or upper <= lower):
                    raise ValueError(f"APIMart: invalid context tiers for {item.get('id')}")
                tier = (f"<={upper}" if lower == 0 else f"{lower}<tokens<={upper}") if upper is not None else (f">{lower}" if lower else "standard")
                row = make_record(source, fetched, item, rates, tier, "listed_base", mapping)
                if row is not None:
                    row.context_limit_tokens = (pricing.get("limits") or {}).get("max_input_tokens")
                    row.notes = "Public APIMart pricing API, USD per 1M tokens; explicit base rates. Group/effective/member discounts excluded; no inferred exchange or multiplier."
                    out.append(row)
                if upper is not None:
                    lower = upper
        return out
