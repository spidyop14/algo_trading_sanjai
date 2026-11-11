from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Quote:
    symbol: str; ltp: float; open: float; high: float; low: float; previous_close: float; change_percent: float; volume: int; source: str; updated_at: datetime; bid: float | None = None; ask: float | None = None; is_live: bool = False
