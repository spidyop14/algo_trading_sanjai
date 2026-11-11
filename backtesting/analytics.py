import math
import pandas as pd

def performance_metrics(initial_capital, equity_curve, trades):
    final = equity_curve[-1]["equity"] if equity_curve else initial_capital; values = pd.Series([x["equity"] for x in equity_curve] or [initial_capital])
    returns = values.pct_change().dropna(); running_max = values.cummax(); drawdown = (values / running_max - 1) * 100
    wins = [t for t in trades if t["net_pnl"] > 0]; losses = [t for t in trades if t["net_pnl"] < 0]; gross_profit = sum(t["net_pnl"] for t in wins); gross_loss = abs(sum(t["net_pnl"] for t in losses))
    sharpe = (returns.mean() / returns.std() * math.sqrt(252)) if len(returns) > 1 and returns.std() else None
    downside = returns[returns < 0].std(); sortino = (returns.mean() / downside * math.sqrt(252)) if len(returns) > 1 and downside else None
    days = max(0, (equity_curve[-1]["timestamp"] - equity_curve[0]["timestamp"]).days) if len(equity_curve) > 1 else 0
    cagr = ((final / initial_capital) ** (365 / days) - 1) * 100 if days >= 30 and initial_capital > 0 else None
    return {"initial_capital": initial_capital, "final_capital": round(final, 2), "net_pnl": round(final - initial_capital, 2), "return_pct": round((final / initial_capital - 1) * 100, 2), "cagr": round(cagr, 2) if cagr is not None else None, "total_trades": len(trades), "winning_trades": len(wins), "losing_trades": len(losses), "win_rate": round(len(wins) / len(trades) * 100, 2) if trades else None, "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None, "average_profit": round(gross_profit / len(wins), 2) if wins else None, "average_loss": round(-gross_loss / len(losses), 2) if losses else None, "max_drawdown": round(float(drawdown.min()), 2), "sharpe": round(float(sharpe), 3) if sharpe is not None else None, "sortino": round(float(sortino), 3) if sortino is not None else None, "transaction_costs": round(sum(t["charges"] for t in trades), 2), "average_holding_minutes": round(sum(t["holding_minutes"] for t in trades) / len(trades), 2) if trades else None, "drawdown": drawdown.tolist()}
