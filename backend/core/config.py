from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = f"sqlite:///{Path(__file__).resolve().parents[2] / 'orbit_algo.db'}"
    paper_trading_only: bool = True
    initial_capital: float = 100_000.0


settings = Settings()
