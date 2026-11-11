from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime

from data.models.quote import Quote


class DataProviderMode(str, Enum): SIMULATION = "SIMULATION"; HISTORICAL = "HISTORICAL"; ZERODHA = "ZERODHA"
class ProviderUnavailable(RuntimeError): pass


class MarketDataProvider(ABC):
    mode: DataProviderMode
    is_live: bool = False
    @abstractmethod
    def quote(self, symbol: str) -> Quote: ...
    @abstractmethod
    def candles(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[dict]: ...
    def health(self) -> dict: return {"mode": self.mode.value, "connected": self.is_live, "live": self.is_live, "error": None}
