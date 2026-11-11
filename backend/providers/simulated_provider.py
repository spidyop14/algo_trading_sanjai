from datetime import date, timedelta
from random import Random

from backend.providers.base_provider import MarketDataProvider, Quote


class SimulatedNSEProvider(MarketDataProvider):
    """Deterministic sample prices. These must never be presented as live NSE data."""
    _prices = {"RELIANCE": 2948.40, "HDFCBANK": 1662.20, "INFY": 1873.60, "TCS": 4218.10, "ICICIBANK": 1326.70, "SBIN": 834.55, "TATAMOTORS": 955.20}

    def quote(self, symbol: str) -> Quote:
        symbol = symbol.upper()
        if symbol not in self._prices:
            raise ValueError(f"Unsupported simulated symbol: {symbol}")
        seed = sum(map(ord, symbol))
        delta = ((seed % 29) - 14) / 100
        return Quote(symbol=symbol, price=self._prices[symbol], change_percent=round(delta, 2), volume=500_000 + seed * 1000)

    def candles(self, symbol: str, days: int = 30) -> list[dict]:
        quote = self.quote(symbol)
        rng = Random(f"orbit-simulated-{symbol}-{days}")
        price, rows = quote.price * .94, []
        for offset in range(days):
            opening = price
            closing = round(max(1, opening * (1 + rng.uniform(-.018, .02))), 2)
            rows.append({"date": (date.today() - timedelta(days=days - offset - 1)).isoformat(), "open": round(opening, 2), "high": round(max(opening, closing) * 1.01, 2), "low": round(min(opening, closing) * .99, 2), "close": closing, "volume": rng.randint(400_000, 3_000_000), "simulated": True})
            price = closing
        return rows
