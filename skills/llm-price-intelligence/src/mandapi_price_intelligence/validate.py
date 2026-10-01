from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
from datetime import date
from urllib.parse import urlparse
from .models import PRICE_COLUMNS


NUMERIC_FIELDS = ["input_per_1m", "output_per_1m", "cache_read_per_1m", "cache_write_per_1m"]
REQUIRED_FIELDS = ["record_id", "model_id", "platform", "currency", "last_checked", "source_url", "verification_status"]


def validate_csv(path: str | Path) -> list[str]:
    errors: list[str] = []
    record_ids = set()
    seen: set[tuple[str, str, str, str, str]] = set()
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return ["CSV has no header"]
        if reader.fieldnames != PRICE_COLUMNS:
            errors.append("CSV columns must match the V2 schema and order")
        for field in REQUIRED_FIELDS:
            if field not in reader.fieldnames:
                errors.append(f"Missing required column: {field}")
        if errors:
            return errors

        for line_no, row in enumerate(reader, start=2):
            for field in REQUIRED_FIELDS:
                if not (row.get(field) or "").strip():
                    errors.append(f"line {line_no}: missing {field}")
            if row.get("record_id") in record_ids:
                errors.append(f"line {line_no}: duplicate record_id")
            record_ids.add(row.get("record_id"))
            if row.get("verification_status") not in {"public_source", "needs_review"}:
                errors.append(f"line {line_no}: unsupported verification_status")
            if row.get("currency") not in {"BRL", "USD", "CNY"}:
                errors.append(f"line {line_no}: unsupported currency")
            try:
                date.fromisoformat(row.get("last_checked", ""))
            except ValueError:
                errors.append(f"line {line_no}: invalid last_checked date")
            url = urlparse(row.get("source_url", ""))
            if url.scheme not in {"http", "https"} or not url.netloc:
                errors.append(f"line {line_no}: invalid source_url")
            for field in NUMERIC_FIELDS:
                value = (row.get(field) or "").strip()
                if not value:
                    continue
                try:
                    if not Decimal(value).is_finite():
                        errors.append(f"line {line_no}: non-finite {field}")
                    elif Decimal(value) < 0:
                        errors.append(f"line {line_no}: negative {field}")
                except InvalidOperation:
                    errors.append(f"line {line_no}: invalid decimal {field}={value!r}")

            if not any((row.get(f) or "").strip() for f in NUMERIC_FIELDS):
                errors.append(f"line {line_no}: no numeric price component")

            key = (
                row.get("platform", ""), row.get("model_id", ""),
                row.get("pricing_variant", ""), row.get("context_tier", ""), row.get("currency", ""),
            )
            if key in seen:
                errors.append(f"line {line_no}: duplicate offer key {key}")
            seen.add(key)
    return errors
