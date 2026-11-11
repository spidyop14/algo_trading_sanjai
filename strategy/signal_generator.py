from dataclasses import dataclass

@dataclass(frozen=True)
class Signal:
    symbol: str; action: str; classification: str; score: int; price: float; stop_loss: float | None; target_price: float | None; risk_reward: float | None; strategy_name: str; source: str; candle_timestamp: object; indicators: dict; confirmations: dict


class SignalScorer:
    weights = {"ema": 30, "rsi": 20, "macd": 20, "volume": 15, "trend": 15}
    def score(self, confirmations: dict[str, bool]) -> int: return sum(self.weights[key] for key, passed in confirmations.items() if passed and key in self.weights)
    def classification(self, score: int) -> str: return "STRONG" if score >= 80 else "MODERATE" if score >= 65 else "NO_TRADE"
