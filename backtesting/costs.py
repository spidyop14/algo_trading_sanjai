from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class TransactionCostConfig:
    """All rates default to zero; users must explicitly set date-effective assumptions."""
    brokerage_pct: float = 0.0; stt_pct: float = 0.0; nse_transaction_pct: float = 0.0; gst_pct: float = 0.0; sebi_pct: float = 0.0; stamp_duty_pct: float = 0.0; dp_charge: float = 0.0; slippage_pct: float = 0.0
    def as_dict(self): return asdict(self)

class IndianEquityCostCalculator:
    def __init__(self, config: TransactionCostConfig): self.config = config
    def execution_price(self, side: str, price: float) -> float:
        return price * (1 + self.config.slippage_pct / 100) if side == "BUY" else price * (1 - self.config.slippage_pct / 100)
    def charges(self, buy_turnover: float, sell_turnover: float) -> float:
        c = self.config; brokerage = (buy_turnover + sell_turnover) * c.brokerage_pct / 100
        transaction = (buy_turnover + sell_turnover) * c.nse_transaction_pct / 100
        gst = (brokerage + transaction) * c.gst_pct / 100
        return round(brokerage + sell_turnover * c.stt_pct / 100 + transaction + gst + (buy_turnover + sell_turnover) * c.sebi_pct / 100 + buy_turnover * c.stamp_duty_pct / 100 + c.dp_charge, 2)
