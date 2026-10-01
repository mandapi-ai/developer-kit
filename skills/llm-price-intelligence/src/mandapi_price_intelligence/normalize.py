from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


PROVIDER_PREFIXES = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "deepseek": "DeepSeek",
    "qwen": "Alibaba",
    "moonshotai": "Moonshot AI",
    "moonshot": "Moonshot AI",
    "minimax": "MiniMax",
    "z-ai": "Zhipu AI",
    "zhipu": "Zhipu AI",
}


def canonicalize_model_id(model_id: str) -> str:
    value = model_id.strip().lower()
    if "/" in value:
        prefix, tail = value.split("/", 1)
        if prefix in PROVIDER_PREFIXES:
            value = tail
    value = value.replace("_", "-")
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")


def infer_model_family(model_id: str, model_name: str = "") -> str:
    value = f"{model_id} {model_name}".lower()
    families = [
        ("claude", "Claude"),
        ("gemini", "Gemini"),
        ("deepseek", "DeepSeek"),
        ("gpt", "GPT"),
        ("kimi", "Kimi"),
        ("moonshot", "Kimi"),
        ("glm", "GLM"),
        ("minimax", "MiniMax"),
        ("qwen", "Qwen"),
        ("mimo", "MiMo"),
    ]
    for needle, family in families:
        if needle in value:
            return family
    return "Other"


def infer_model_provider(model_id: str, model_name: str = "") -> str:
    if "/" in model_id:
        prefix = model_id.split("/", 1)[0].lower()
        if prefix in PROVIDER_PREFIXES:
            return PROVIDER_PREFIXES[prefix]
    family = infer_model_family(model_id, model_name)
    return {
        "GPT": "OpenAI",
        "Claude": "Anthropic",
        "Gemini": "Google",
        "DeepSeek": "DeepSeek",
        "Kimi": "Moonshot AI",
        "GLM": "Zhipu AI",
        "MiniMax": "MiniMax",
        "Qwen": "Alibaba",
        "MiMo": "Xiaomi",
    }.get(family, "")


def detect_currency(text: str, default: str) -> str:
    t = text.upper()
    if "R$" in t or "BRL" in t:
        return "BRL"
    if "US$" in t or "USD" in t:
        return "USD"
    if "CNY" in t or "RMB" in t or "¥" in text:
        return "CNY"
    if "$" in text:
        return "USD"
    return default


def parse_decimal_price(text: str) -> Decimal | None:
    """Parse a visible money/number string without guessing units."""
    if text is None:
        return None
    s = str(text).strip()
    s = re.split(r"(?:\bper\s+|/\s*)(?:1m|1k|million|milhão|1000|token|image|second|request)", s, maxsplit=1, flags=re.I)[0].strip()
    if not s or s.lower() in {"-", "n/a", "na", "null", "none", "sob consulta", "contact sales"}:
        return None

    if re.search(r"sob\s+(?:consulta|proposta)|contact\s+sales|quote|a partir|starting|from\s+[$¥]|\d[\d.,]*\s*(?:[-–—]|to|até)\s*[$¥]?\s*\d", s, re.I):
        return None
    match = re.search(r"[-+]?\d[\d\s.,]*(?:[eE][-+]?\d+)?", s)
    if not match:
        return None
    num = match.group(0).replace(" ", "")

    if "," in num and "." in num:
        if num.rfind(",") > num.rfind("."):
            num = num.replace(".", "").replace(",", ".")
        else:
            num = num.replace(",", "")
    elif "," in num:
        num = num.replace(".", "").replace(",", ".")

    try:
        number = Decimal(num)
        return number if number.is_finite() and number >= 0 else None
    except InvalidOperation:
        return None


def per_token_to_per_million(value: str | int | float | Decimal | None) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
        return number * Decimal(1_000_000) if number.is_finite() and number >= 0 else None
    except (InvalidOperation, ValueError):
        return None
