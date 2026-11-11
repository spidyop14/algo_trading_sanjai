import json
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo
from sqlalchemy import select
from backend.database.repositories import get_or_create_paper_account
from broker.exceptions import AuthenticationRequired, BrokerError, LiveExecutionDisabled, TokenExpired
from broker.models import BrokerConnection
from broker.security import decrypt_token, encrypt_token

IST = ZoneInfo("Asia/Kolkata")
class ZerodhaBrokerService:
    """Official SDK adapter. No order method can submit a live order in Phase 7."""
    def __init__(self, session, kite_factory=None): self.session, self.kite_factory = session, kite_factory
    def _credentials(self):
        key, secret = os.getenv("KITE_API_KEY"), os.getenv("KITE_API_SECRET")
        if not key or not secret: raise AuthenticationRequired("Zerodha credentials are not configured on this server")
        return key, secret
    def _kite(self, access_token=None):
        key, _ = self._credentials()
        if self.kite_factory: kite = self.kite_factory(key)
        else:
            try:
                from kiteconnect import KiteConnect
                kite = KiteConnect(api_key=key)
            except ImportError as error: raise BrokerError("kiteconnect SDK is not installed") from error
        if access_token: kite.set_access_token(access_token)
        return kite
    def connection(self):
        account = get_or_create_paper_account(self.session); item = self.session.scalar(select(BrokerConnection).where(BrokerConnection.account_id == account.id))
        if not item: item = BrokerConnection(account_id=account.id); self.session.add(item); self.session.flush()
        return item
    def login_url(self): return self._kite().login_url()
    def complete_login(self, request_token: str):
        if not request_token: raise AuthenticationRequired("Request token is required")
        key, secret = self._credentials(); kite = self._kite(); data = kite.generate_session(request_token, api_secret=secret); access = data.get("access_token")
        if not access: raise BrokerError("Broker did not return an access token")
        item = self.connection(); item.encrypted_access_token = encrypt_token(access); item.status = "CONNECTED"; item.profile_json = json.dumps({k:v for k,v in data.items() if k not in {"access_token", "public_token"}}); item.token_expires_at = datetime.combine(datetime.now(IST).date(), time(23,59), tzinfo=IST); item.last_error = None; return item
    def client(self):
        item = self.connection()
        if not item.encrypted_access_token: raise AuthenticationRequired("Zerodha authentication is required")
        if item.token_expires_at and item.token_expires_at.astimezone(IST) <= datetime.now(IST): item.status = "TOKEN_EXPIRED"; raise TokenExpired("Zerodha access token has expired; authenticate again")
        return self._kite(decrypt_token(item.encrypted_access_token))
    def sync_account(self):
        kite = self.client(); item = self.connection()
        try:
            data = {"profile": kite.profile(), "margins": kite.margins(), "holdings": kite.holdings(), "positions": kite.positions(), "orders": kite.orders(), "trades": kite.trades()}
            item.profile_json, item.last_synced_at, item.status, item.last_error = json.dumps(data["profile"]), datetime.now(IST), "CONNECTED", None; return data
        except Exception as error:
            item.status, item.last_error = "CONNECTION_ERROR", "Broker request failed"; raise BrokerError("Unable to refresh Zerodha account data") from error
    def instruments(self): return self.client().instruments("NSE")
    def disconnect(self):
        item = self.connection(); item.encrypted_access_token = None; item.token_expires_at = None; item.status = "DISCONNECTED"; item.profile_json = None
    def validate_order(self, symbol, side, quantity, order_type):
        if side not in {"BUY", "SELL"} or quantity <= 0 or order_type not in {"MARKET", "LIMIT", "SL", "SL-M"}: raise BrokerError("Invalid broker order request")
        return {"symbol": symbol.upper(), "side": side, "quantity": quantity, "order_type": order_type, "execution_enabled": False}
    def place_order(self, *args, **kwargs): raise LiveExecutionDisabled("Live broker order placement is disabled until explicit Phase 8 authorization")
    def modify_order(self, *args, **kwargs): raise LiveExecutionDisabled("Live broker order modification is disabled until Phase 8")
    def cancel_order(self, *args, **kwargs): raise LiveExecutionDisabled("Live broker order cancellation is disabled until Phase 8")
