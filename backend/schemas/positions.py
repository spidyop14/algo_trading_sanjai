from dataclasses import dataclass

@dataclass(frozen=True)
class PositionView:
    symbol: str; quantity: int; average_entry_price: float; current_price: float; market_value: float; unrealised_pnl: float; realised_pnl: float
