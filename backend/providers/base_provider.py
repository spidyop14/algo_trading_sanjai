from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    change_percent: float
    volume: int
    simulated: bool = True


class MarketDataProvider(ABC):
    is_live = False

    @abstractmethod
    def quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    def candles(self, symbol: str, days: int = 30) -> list[dict]: ...
