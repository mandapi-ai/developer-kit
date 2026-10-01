from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


PRICE_FIELDS = ["input_per_1m", "output_per_1m", "cache_read_per_1m", "cache_write_per_1m"]


def _key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("platform", ""),
        row.get("model_id", ""),
        row.get("pricing_variant", ""),
        row.get("context_tier", ""),
        row.get("currency", ""),
    )


def _load(path: str | Path) -> dict[tuple[str, str, str, str, str], dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        rows = {}
        for row in csv.DictReader(f):
            key = _key(row)
            if key in rows:
                raise ValueError(f"Duplicate offer key in {path}: {key}")
            rows[key] = row
        return rows


def _decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        number = Decimal(value)
        if not number.is_finite() or number < 0:
            raise ValueError(f"Invalid price: {value}")
        return number
    except InvalidOperation as exc:
        raise ValueError(f"Invalid price: {value}") from exc


def build_diff_markdown(old_path: str | Path, new_path: str | Path) -> str:
    old, new = _load(old_path), _load(new_path)
    unavailable = set()
    evidence_path = Path(new_path).with_name("evidence.jsonl")
    if evidence_path.exists():
        for line in evidence_path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if not item.get("ok") or item.get("parser_status") in {"parse_error", "no_supported_prices", "not_attempted"}:
                unavailable.add(item["platform"])
    added = sorted(set(new) - set(old))
    unobserved = sorted(key for key in set(old) - set(new) if key[0] in unavailable)
    removed = sorted(key for key in set(old) - set(new) if key[0] not in unavailable)
    changes: list[tuple[tuple[str, str, str, str, str], str, Decimal | None, Decimal | None]] = []

    for key in sorted(set(old) & set(new)):
        for field in PRICE_FIELDS:
            before, after = _decimal(old[key].get(field)), _decimal(new[key].get(field))
            if before != after:
                changes.append((key, field, before, after))

    lines = [
        "# LLM API Price Changes",
        "",
        f"- Added offers: **{len(added)}**",
        f"- Removed offers: **{len(removed)}**",
        f"- Price component changes: **{len(changes)}**",
        f"- Unobserved offers from unavailable sources: **{len(unobserved)}**",
        "",
    ]

    lines += ["Removed means absent from these comparable CSV observations, not confirmed discontinued. Check source completeness before publishing.", ""]
    if not evidence_path.exists():
        lines += ["No adjacent evidence.jsonl found; source failures and catalog completeness cannot be assessed.", ""]
    if unobserved:
        lines += ["## Unobserved (source unavailable)", ""] + [f"- `{key}`" for key in unobserved] + [""]
    if added:
        lines += ["## Added", ""] + [f"- `{key}`" for key in added] + [""]
    if removed:
        lines += ["## Removed", ""] + [f"- `{key}`" for key in removed] + [""]
    if changes:
        lines += ["## Changed", ""]
        for key, field, before, after in changes:
            def fmt(x: Decimal | None) -> str:
                return "missing" if x is None else format(x, "f")
            lines.append(f"- `{key}` — **{field}**: {fmt(before)} → {fmt(after)}")
        lines.append("")
    return "\n".join(lines)
