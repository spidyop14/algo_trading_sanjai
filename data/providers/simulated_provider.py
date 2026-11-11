from datetime import datetime, timedelta
from random import Random
from zoneinfo import ZoneInfo

from data.models.quote import Quote
from data.providers.base_provider import DataProviderMode, MarketDataProvider

IST = ZoneInfo("Asia/Kolkata")


class SimulatedMarketDataProvider(MarketDataProvider):
    """Deterministic synthetic data. It is never a live quote source."""
    mode, is_live = DataProviderMode.SIMULATION, False
    prices = {"RELIANCE": 2948.40, "HDFCBANK": 1662.20, "INFY": 1873.60, "TCS": 4218.10, "ICICIBANK": 1326.70, "SBIN": 834.55, "TATAMOTORS": 955.20}
    def quote(self, symbol: str) -> Quote:
        symbol = symbol.upper()
        if symbol not in self.prices: raise ValueError(f"Unsupported simulated symbol: {symbol}")
        seed = sum(map(ord, symbol)); ltp = self.prices[symbol]; prior = round(ltp * (1 - ((seed % 25 - 12) / 1000)), 2)
        return Quote(symbol, ltp, round(prior * .998, 2), round(ltp * 1.012, 2), round(ltp * .988, 2), prior, round((ltp - prior) / prior * 100, 2), 500_000 + seed * 1_000, "SIMULATION", datetime.now(IST), round(ltp - .05, 2), round(ltp + .05, 2), False)
    def candles(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[dict]:
        if timeframe not in {"1m", "3m", "5m", "15m", "30m", "1h", "1d"}: raise ValueError("Unsupported timeframe")
        quote = self.quote(symbol); step = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "1d": 1440}[timeframe]
        rng, cursor, value, result = Random(f"{symbol}-{timeframe}-{start.date()}"), start.astimezone(IST), quote.previous_close * .98, []
        while cursor <= end.astimezone(IST):
            opening = value; closing = round(max(1, opening * (1 + rng.uniform(-.008, .009))), 2)
            result.append({"symbol": symbol.upper(), "timestamp": cursor, "open": round(opening, 2), "high": round(max(opening, closing) * 1.003, 2), "low": round(min(opening, closing) * .997, 2), "close": closing, "volume": rng.randint(20_000, 500_000), "source": "SIMULATION"})
            value, cursor = closing, cursor + timedelta(minutes=step)
        return result
