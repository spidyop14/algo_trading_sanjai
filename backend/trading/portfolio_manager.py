from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import Portfolio, Position, TradingAccount
from backend.providers.base_provider import MarketDataProvider
from backend.schemas.portfolio import PortfolioSummary


class PortfolioManager:
    def __init__(self, session: Session, provider: MarketDataProvider): self.session, self.provider = session, provider

    def summary(self, account: TradingAccount) -> PortfolioSummary:
        positions = list(self.session.scalars(select(Position).where(Position.account_id == account.id, Position.quantity != 0)))
        invested = unrealised = 0.0
        for p in positions:
            current = self.provider.quote(p.symbol).price
            invested += abs(p.quantity) * p.average_entry_price
            unrealised += (current - p.average_entry_price) * p.quantity
        realised = self.session.get(Portfolio, account.id).realised_pnl
        total = account.cash_balance + sum(self.provider.quote(p.symbol).price * p.quantity for p in positions)
        return PortfolioSummary(account.initial_capital, account.cash_balance, invested, realised, unrealised, total, (unrealised / account.initial_capital) * 100, ((total - account.initial_capital) / account.initial_capital) * 100)
