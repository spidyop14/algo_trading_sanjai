from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base
from data.models.candle import Candle
from data.providers.base_provider import DataProviderMode, ProviderUnavailable
from data.providers.csv_provider import CSVMarketDataProvider
from data.providers.simulated_provider import SimulatedMarketDataProvider
from data.providers.zerodha_provider import ZerodhaMarketDataProvider
from data.services.historical_data_service import HistoricalDataService
from data.services.instrument_service import InstrumentService
from data.services.market_data_service import MarketDataService
from data.utils.data_validator import validate_candle
from data.utils.market_calendar import NSEMarketCalendar

IST = ZoneInfo("Asia/Kolkata")

@pytest.fixture()
def market_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()

def test_simulated_quote_and_candles_are_labelled():
    provider = SimulatedMarketDataProvider()
    quote = provider.quote("RELIANCE")
    rows = provider.candles("RELIANCE", "1d", datetime(2026, 1, 1, tzinfo=IST), datetime(2026, 1, 3, tzinfo=IST))
    assert quote.source == "SIMULATION" and quote.is_live is False
    assert len(rows) == 3 and all(row["source"] == "SIMULATION" for row in rows)

def test_historical_cache_prevents_duplicate_candles(market_session):
    service = HistoricalDataService(market_session, SimulatedMarketDataProvider())
    start, end = datetime(2026, 1, 1, tzinfo=IST), datetime(2026, 1, 3, tzinfo=IST)
    first = service.candles("RELIANCE", "1d", start, end, refresh=True)
    second = service.candles("RELIANCE", "1d", start, end, refresh=True)
    assert len(first) == len(second) == 3
    assert market_session.scalar(select(func.count(Candle.id))) == 3
    assert len(service.missing_timestamps("RELIANCE", "1d", [start, start + timedelta(days=1), start + timedelta(days=2)])) == 0

def test_csv_import_and_quote(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text("symbol,timestamp,open,high,low,close,volume\nRELIANCE,2026-01-01T09:15:00+05:30,100,105,99,104,1000\nRELIANCE,2026-01-02T09:15:00+05:30,104,108,103,106,2000\n", encoding="utf-8")
    provider = CSVMarketDataProvider(path)
    assert provider.quote("RELIANCE").ltp == 106
    assert len(provider.candles("RELIANCE", "1d", datetime(2026, 1, 1, tzinfo=IST), datetime(2026, 1, 3, tzinfo=IST))) == 2

def test_validator_rejects_invalid_ohlc():
    with pytest.raises(ValueError, match="OHLC"):
        validate_candle({"timestamp": datetime.now(IST), "open": 100, "high": 90, "low": 95, "close": 98, "volume": 1})

def test_calendar_is_timezone_and_weekend_aware():
    calendar = NSEMarketCalendar({"2026-01-26"})
    assert calendar.status(datetime(2026, 1, 5, 9, 14, tzinfo=IST)) == "PRE_MARKET"
    assert calendar.status(datetime(2026, 1, 5, 9, 15, tzinfo=IST)) == "OPEN"
    assert calendar.status(datetime(2026, 1, 3, 11, 0, tzinfo=IST)) == "CLOSED"
    assert calendar.status(datetime(2026, 1, 26, 11, 0, tzinfo=IST)) == "CLOSED"

def test_instrument_master_imports_without_invented_tokens(market_session):
    service = InstrumentService(market_session)
    assert service.import_master("data/instruments/nse_universe.csv") == 7
    reliance = service.list("NIFTY50")[0]
    assert reliance.exchange == "NSE" and reliance.instrument_token is None

def test_zerodha_is_disabled_and_mocked_client_path_works():
    with pytest.raises(ProviderUnavailable, match="disabled"):
        ZerodhaMarketDataProvider().quote("RELIANCE")
    class FakeKite:
        def quote(self, instruments): return {instruments[0]: {"last_price": 100, "ohlc": {"open": 99, "high": 101, "low": 98, "close": 98}, "volume": 55, "net_change": 2}}
    quote = ZerodhaMarketDataProvider(FakeKite(), {"RELIANCE": 1}).quote("RELIANCE")
    assert quote.ltp == 100 and quote.source == "ZERODHA" and quote.is_live

def test_market_service_reports_simulation_not_live(market_session):
    health = MarketDataService(market_session, DataProviderMode.SIMULATION).health()
    assert health["mode"] == "SIMULATION" and health["live"] is False
