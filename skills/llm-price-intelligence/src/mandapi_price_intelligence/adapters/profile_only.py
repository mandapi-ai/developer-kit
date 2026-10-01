from __future__ import annotations

from .base import Adapter
from ..fetch import FetchResult
from ..models import PriceRecord, SourceSpec


class ProfileOnlyAdapter(Adapter):
    def parse(self, source: SourceSpec, fetched: FetchResult) -> list[PriceRecord]:
        # The platform belongs in providers.csv / market research, but no numeric
        # price row is created without a supported public numeric source.
        return []
