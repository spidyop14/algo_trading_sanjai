from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import DailyPerformance, Portfolio, RiskSetting, Strategy, SystemLog, TradingAccount, TradingSignal, User


def get_or_create_paper_account(session: Session, initial_capital: float = 100000.0) -> TradingAccount:
    account = session.scalar(select(TradingAccount).where(TradingAccount.name == "ORBIT Paper Account"))
    if account:
        _seed_dashboard_defaults(session)
        return account
    user = User(email="paper@orbitalgo.local", display_name="Paper Trader")
    account = TradingAccount(user=user, name="ORBIT Paper Account", initial_capital=initial_capital, cash_balance=initial_capital, is_paper=True)
    session.add_all([user, account])
    session.flush()
    session.add_all([Portfolio(account_id=account.id), RiskSetting(account_id=account.id)])
    _seed_dashboard_defaults(session)
    return account


def _seed_dashboard_defaults(session: Session) -> None:
    if not session.scalar(select(Strategy.id).limit(1)):
        session.add_all([
            Strategy(name="EMA crossover", active=True, win_rate=64.0, trades=28, profit_factor=1.82),
            Strategy(name="RSI momentum", active=True, win_rate=59.0, trades=19, profit_factor=1.47),
            Strategy(name="MACD confirmation", active=False, win_rate=52.0, trades=14, profit_factor=1.21),
        ])
    if not session.scalar(select(TradingSignal.id).limit(1)):
        session.add_all([
            TradingSignal(symbol="RELIANCE", signal="BUY", entry_price=2948.40, target_price=3025.00, stop_loss=2850.00),
            TradingSignal(symbol="ICICIBANK", signal="SELL", entry_price=1326.70, target_price=1290.00, stop_loss=1360.00),
        ])


def list_performance(session: Session, account_id: int) -> list[DailyPerformance]:
    return list(session.scalars(select(DailyPerformance).where(DailyPerformance.account_id == account_id).order_by(DailyPerformance.trade_date)))


def record_system_log(session: Session, level: str, event: str, message: str) -> None:
    """Persist non-sensitive operational events; never pass credentials here."""
    session.add(SystemLog(level=level, event=event, message=message))
