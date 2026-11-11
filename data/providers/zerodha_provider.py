import time
from datetime import datetime

from data.providers.base_provider import DataProviderMode, MarketDataProvider, ProviderUnavailable
from data.models.quote import Quote


class ZerodhaMarketDataProvider(MarketDataProvider):
    """Kite SDK adapter. Disabled unless an authenticated Kite client is injected."""
    mode, is_live = DataProviderMode.ZERODHA, False
    def __init__(self, kite_client=None, instrument_tokens: dict[str, int] | None = None, retries: int = 3):
        self.kite, self.instrument_tokens, self.retries = kite_client, instrument_tokens or {}, retries
    def _client(self):
        if not self.kite: raise ProviderUnavailable("Zerodha provider is disabled: no authenticated Kite client configured")
        return self.kite
    def _retry(self, fn):
        error = None
        for attempt in range(self.retries):
            try: return fn()
            except Exception as exc:
                error = exc
                if attempt < self.retries - 1: time.sleep(0.1 * (2 ** attempt))
        raise ProviderUnavailable(f"Zerodha request failed after retries: {error}")
    def quote(self, symbol: str) -> Quote:
        self._client()
        token = self.instrument_tokens.get(symbol.upper())
        if not token: raise ProviderUnavailable(f"No verified instrument token configured for {symbol}")
        data = self._retry(lambda: self._client().quote([f"NSE:{symbol.upper()}"]))[f"NSE:{symbol.upper()}"]
        ohlc = data["ohlc"]; depth = data.get("depth", {})
        bid = depth.get("buy", [{}])[0].get("price") if depth.get("buy") else None; ask = depth.get("sell", [{}])[0].get("price") if depth.get("sell") else None
        return Quote(symbol.upper(), data["last_price"], ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"], data.get("net_change", 0) / ohlc["close"] * 100, data.get("volume", 0), "ZERODHA", datetime.now().astimezone(), bid, ask, True)
    def candles(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[dict]:
        self._client()
        token = self.instrument_tokens.get(symbol.upper())
        if not token: raise ProviderUnavailable(f"No verified instrument token configured for {symbol}")
        raw = self._retry(lambda: self._client().historical_data(token, start, end, timeframe))
        return [{"symbol": symbol.upper(), "timestamp": row["date"], "open": row["open"], "high": row["high"], "low": row["low"], "close": row["close"], "volume": row["volume"], "source": "ZERODHA"} for row in raw]
    def health(self) -> dict: return {"mode": self.mode.value, "connected": bool(self.kite), "live": bool(self.kite), "error": None if self.kite else "Disabled until authenticated Kite client is configured"}
