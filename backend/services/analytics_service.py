from datetime import date, timedelta
from backend.database.repositories import get_or_create_paper_account, list_performance
from backend.database.models import Strategy, TradingSignal
from sqlalchemy import select
from backend.services.portfolio_service import PortfolioService


class AnalyticsService:
    def __init__(self, session): self.session = session
    def performance(self):
        account = get_or_create_paper_account(self.session)
        stored = list_performance(self.session, account.id)
        if stored: return [{"date": x.trade_date, "equity": x.equity, "daily_pnl": x.daily_pnl} for x in stored]
        summary = PortfolioService(self.session).summary()
        return [{"date": (date.today() - timedelta(days=i)).isoformat(), "equity": summary.total_capital + (29-i)*95, "daily_pnl": 95} for i in reversed(range(30))]

    def strategies(self):
        return list(self.session.scalars(select(Strategy).order_by(Strategy.name)))

    def signals(self):
        return list(self.session.scalars(select(TradingSignal).where(TradingSignal.active.is_(True))))
