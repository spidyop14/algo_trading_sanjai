import pandas as pd

LEDGER_COLUMNS = ["symbol", "strategy", "entry_time", "exit_time", "entry_price", "exit_price", "quantity", "gross_pnl", "charges", "net_pnl", "exit_reason", "holding_minutes"]

def trade_ledger_csv(trades: list[dict]) -> bytes:
    return pd.DataFrame(trades, columns=LEDGER_COLUMNS).to_csv(index=False).encode("utf-8")
