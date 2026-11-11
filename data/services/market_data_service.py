from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from data.providers.base_provider import DataProviderMode, MarketDataProvider, ProviderUnavailable
from data.providers.csv_provider import CSVMarketDataProvider
from data.providers.simulated_provider import SimulatedMarketDataProvider
from data.providers.zerodha_provider import ZerodhaMarketDataProvider
from data.services.historical_data_service import HistoricalDataService
from data.utils.market_calendar import NSEMarketCalendar


class MarketDataService:
    def __init__(self, session: Session, mode: DataProviderMode = DataProviderMode.SIMULATION, csv_path=None, kite_client=None, instrument_tokens=None):
        self.session, self.mode = session, mode
        self.provider: MarketDataProvider = SimulatedMarketDataProvider() if mode == DataProviderMode.SIMULATION else (CSVMarketDataProvider(csv_path) if mode == DataProviderMode.HISTORICAL else ZerodhaMarketDataProvider(kite_client, instrument_tokens))
    def quote(self, symbol: str): return self.provider.quote(symbol)
    def scanner(self, symbols: list[str] | None = None):
        symbols = symbols or list(getattr(self.provider, "prices", {}))
        return [self.provider.quote(symbol) for symbol in symbols]
    def candles(self, symbol: str, timeframe: str, start: datetime | None = None, end: datetime | None = None):
        end = end or datetime.now().astimezone(); start = start or end - timedelta(days=30)
        return HistoricalDataService(self.session, self.provider).candles(symbol, timeframe, start, end)
    def health(self) -> dict:
        value = self.provider.health(); value.update({"market_status": NSEMarketCalendar().status(), "last_successful_update": datetime.now().astimezone().isoformat() if value["connected"] or self.mode != DataProviderMode.ZERODHA else None})
        return value
