import csv
from datetime import datetime
from pathlib import Path

from data.models.quote import Quote
from data.providers.base_provider import DataProviderMode, MarketDataProvider, ProviderUnavailable
from data.utils.data_validator import validate_candle


class CSVMarketDataProvider(MarketDataProvider):
    mode, is_live = DataProviderMode.HISTORICAL, False
    def __init__(self, path: str | Path): self.path = Path(path); self._rows = self._load()
    def _load(self) -> list[dict]:
        if not self.path.exists(): raise ProviderUnavailable("Historical CSV is not configured")
        rows = []
        with self.path.open(newline="", encoding="utf-8") as handle:
            for raw in csv.DictReader(handle):
                item = {"symbol": raw["symbol"].upper(), "timestamp": datetime.fromisoformat(raw["timestamp"]), "open": float(raw["open"]), "high": float(raw["high"]), "low": float(raw["low"]), "close": float(raw["close"]), "volume": int(raw["volume"]), "source": "HISTORICAL"}
                validate_candle(item); rows.append(item)
        return rows
    def quote(self, symbol: str) -> Quote:
        rows = [r for r in self._rows if r["symbol"] == symbol.upper()]
        if not rows: raise ProviderUnavailable(f"No historical quote for {symbol}")
        current, previous = rows[-1], rows[-2] if len(rows) > 1 else rows[-1]
        return Quote(current["symbol"], current["close"], current["open"], current["high"], current["low"], previous["close"], round((current["close"] - previous["close"]) / previous["close"] * 100, 2), current["volume"], "HISTORICAL", current["timestamp"], is_live=False)
    def candles(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[dict]:
        if timeframe != "1d": raise ProviderUnavailable("CSV provider accepts imported 1d candles only")
        return [r for r in self._rows if r["symbol"] == symbol.upper() and start <= r["timestamp"] <= end]
