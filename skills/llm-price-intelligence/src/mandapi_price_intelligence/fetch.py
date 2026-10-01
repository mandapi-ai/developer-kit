from __future__ import annotations

import hashlib
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from .models import Evidence, SourceSpec


@dataclass(slots=True)
class FetchResult:
    text: str
    json_data: Any | None
    evidence: Evidence


class PublicFetcher:
    def __init__(self, user_agent: str, timeout_seconds: int = 20):
        self.client = httpx.Client(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers={"User-Agent": user_agent, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"},
        )

    def close(self) -> None:
        self.client.close()

    def fetch(self, source: SourceSpec) -> FetchResult:
        now = datetime.now(timezone.utc).isoformat()
        try:
            response = self.client.get(source.pricing_url)
            body = response.content
            digest = hashlib.sha256(body).hexdigest()
            content_type = response.headers.get("content-type", "")
            if response.is_error:
                return FetchResult("", None, Evidence(
                    source_id=source.id, platform=source.platform, url=str(response.url),
                    fetched_at=now, status_code=response.status_code, sha256=digest,
                    adapter=source.adapter, ok=False, content_type=content_type,
                    error=f"HTTP {response.status_code}",
                ))
            json_data = None
            if "json" in content_type.lower():
                try:
                    json_data = response.json(parse_float=Decimal)
                except ValueError:
                    json_data = None
            return FetchResult(
                text=response.text,
                json_data=json_data,
                evidence=Evidence(
                    source_id=source.id,
                    platform=source.platform,
                    url=str(response.url),
                    fetched_at=now,
                    status_code=response.status_code,
                    sha256=digest,
                    adapter=source.adapter,
                    ok=True,
                    content_type=content_type,
                ),
            )
        except Exception as exc:  # network failures become evidence, not fake records
            return FetchResult(
                text="",
                json_data=None,
                evidence=Evidence(
                    source_id=source.id,
                    platform=source.platform,
                    url=source.pricing_url,
                    fetched_at=now,
                    status_code=None,
                    sha256=None,
                    adapter=source.adapter,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                ),
            )
