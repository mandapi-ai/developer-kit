from __future__ import annotations

from abc import ABC, abstractmethod

from ..fetch import FetchResult
from ..models import PriceRecord, SourceSpec


class Adapter(ABC):
    @abstractmethod
    def parse(self, source: SourceSpec, fetched: FetchResult) -> list[PriceRecord]:
        raise NotImplementedError
