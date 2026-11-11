from datetime import datetime, timedelta, timezone
import os
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base
from broker.exceptions import AuthenticationRequired, LiveExecutionDisabled, TokenExpired
from broker.zerodha import ZerodhaBrokerService

class FakeKite:
    def __init__(self, key): self.key = key; self.token = None
    def login_url(self): return "https://kite.example/login"
    def set_access_token(self, value): self.token = value
    def generate_session(self, request_token, api_secret): return {"access_token": "secret-token", "user_id": "AB1234"}
    def profile(self): return {"user_id": "AB1234"}
    def margins(self): return {"equity": {"available": {"cash": 1}}}
    def holdings(self): return []
    def positions(self): return {"net": []}
    def orders(self): return []
    def trades(self): return []
    def instruments(self, exchange): return []

@pytest.fixture()
def service(monkeypatch):
    monkeypatch.setenv("KITE_API_KEY", "key"); monkeypatch.setenv("KITE_API_SECRET", "secret"); monkeypatch.setenv("ORBIT_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine); session = sessionmaker(bind=engine)(); yield ZerodhaBrokerService(session, FakeKite); session.close()

def test_login_url_and_secure_token_flow(service):
    assert service.login_url().startswith("https://")
    item = service.complete_login("request")
    assert item.status == "CONNECTED" and "secret-token" not in item.encrypted_access_token
    assert service.client().token == "secret-token"

def test_profile_account_sync_and_instruments(service):
    service.complete_login("request"); data = service.sync_account()
    assert data["profile"]["user_id"] == "AB1234" and service.instruments() == []

def test_missing_credentials_expiry_and_disabled_orders(service, monkeypatch):
    monkeypatch.delenv("KITE_API_KEY")
    with pytest.raises(AuthenticationRequired): service.login_url()
    monkeypatch.setenv("KITE_API_KEY", "key"); service.complete_login("request"); service.connection().token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    with pytest.raises(TokenExpired): service.client()
    with pytest.raises(LiveExecutionDisabled): service.place_order()
    assert service.validate_order("INFY", "BUY", 1, "MARKET")["execution_enabled"] is False
