from __future__ import annotations

from pathlib import Path

import yaml

from .models import SourceSpec


def load_registry(path: str | Path) -> tuple[dict, list[SourceSpec]]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("sources"), list):
        raise ValueError("sources.yaml must contain a top-level 'sources' list")

    timeout = raw.get("default_timeout_seconds", 20)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ValueError("default_timeout_seconds must be positive")
    specs: list[SourceSpec] = []
    required = {
        "id", "platform", "enabled", "adapter", "pricing_url", "platform_type",
        "source_type", "default_currency", "market_scope", "brazil_relevance",
        "openai_compatible",
    }
    seen = set()
    for index, item in enumerate(raw["sources"]):
        if not isinstance(item, dict):
            raise ValueError(f"Source {index}: expected a mapping")
        missing = required - set(item)
        if missing:
            raise ValueError(f"Source is missing required keys {sorted(missing)}: {item}")
        for key in required - {"enabled", "openai_compatible"}:
            if not isinstance(item[key], str) or not item[key].strip():
                raise ValueError(f"Source {index}: {key} must be a non-empty string")
        if item["default_currency"] not in {"BRL", "USD", "CNY"}:
            raise ValueError(f"Source {item['id']}: unsupported currency")
        if item.get("unit") not in {None, "per_1m_tokens", "per_token"}:
            raise ValueError(f"Source {item['id']}: unsupported unit")
        if item["id"] in seen:
            raise ValueError(f"Duplicate source ID: {item['id']}")
        seen.add(item["id"])
        if item["adapter"] not in {"openrouter", "generic_html", "profile_only", "roteia", "runapi", "kunavo", "tokenrecarga", "apimart", "ominigate", "openai", "anthropic", "google_ai_studio", "deepseek"}:
            raise ValueError(f"Source {item['id']}: unknown adapter {item['adapter']}")
        if not str(item["pricing_url"]).startswith(("https://", "http://")):
            raise ValueError(f"Source {item['id']}: pricing_url must be a public HTTP URL")
        for flag in ("enabled", "openai_compatible"):
            if not isinstance(item[flag], bool):
                raise ValueError(f"Source {item['id']}: {flag} must be boolean")
        known = {k: item.get(k) for k in required | {"unit"}}
        extra = {k: v for k, v in item.items() if k not in known}
        specs.append(SourceSpec(**known, extra=extra))
    return raw, specs
