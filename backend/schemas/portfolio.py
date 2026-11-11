from dataclasses import dataclass

@dataclass(frozen=True)
class PortfolioSummary:
    total_capital: float; available_balance: float; invested_capital: float; realised_pnl: float; unrealised_pnl: float; total_value: float; daily_return_pct: float; overall_return_pct: float
