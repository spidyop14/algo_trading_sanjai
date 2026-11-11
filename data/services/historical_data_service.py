from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models.candle import Candle
from data.providers.base_provider import MarketDataProvider
from data.utils.data_validator import validate_candle, validate_timeframe


class HistoricalDataService:
    def __init__(self, session: Session, provider: MarketDataProvider): self.session, self.provider = session, provider
    def candles(self, symbol: str, timeframe: str, start: datetime, end: datetime, refresh: bool = False) -> list[Candle]:
        validate_timeframe(timeframe)
        query = select(Candle).where(Candle.symbol == symbol.upper(), Candle.timeframe == timeframe, Candle.timestamp >= start, Candle.timestamp <= end).order_by(Candle.timestamp)
        cached = list(self.session.scalars(query))
        if cached and not refresh: return cached
        incoming = self.provider.candles(symbol, timeframe, start, end)
        for item in incoming:
            validate_candle(item)
            exists = self.session.scalar(select(Candle).where(Candle.symbol == item["symbol"], Candle.timeframe == timeframe, Candle.timestamp == item["timestamp"], Candle.source == item["source"]))
            if not exists: self.session.add(Candle(timeframe=timeframe, **item))
        self.session.flush()
        return list(self.session.scalars(query))
    def missing_timestamps(self, symbol: str, timeframe: str, expected: list[datetime]) -> list[datetime]:
        actual = set(self.session.scalars(select(Candle.timestamp).where(Candle.symbol == symbol.upper(), Candle.timeframe == timeframe)))
        # SQLite stores DATE/TIME without timezone offsets; compare the persisted
        # local wall time while providers retain timezone-aware input validation.
        return [stamp for stamp in expected if stamp.replace(tzinfo=None) not in actual]
