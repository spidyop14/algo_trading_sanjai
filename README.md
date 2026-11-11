# ORBIT ALGO dashboard

Premium Streamlit UI and modular Python backend for a simulated NSE algorithmic-trading workspace. It is deliberately paper-only: it does not fetch live market data, connect to a broker, or place real orders.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

The SQLite schema is automatically initialized on first launch. It persists users, accounts, portfolio state, orders, positions, fills, risk controls, performance, strategies, signals and system logs in `orbit_algo.db`.

## Architecture

- `backend/providers`: a provider interface and deterministic `SimulatedNSEProvider`; every quote is simulated.
- `backend/trading`: paper-only order lifecycle, position accounting, portfolio calculations and risk validation.
- `backend/services`: dashboard-facing read/write façade.
- `backend/database`: SQLAlchemy models, repository helpers and initial SQLite migration.
- `tests`: order lifecycle, cancellation, partial fills/exits, duplicate prevention, daily-loss and portfolio checks.

## Market data modes (Phase 3)

- **SIMULATION** (default): deterministic synthetic prices and OHLCV, explicitly labelled as simulated.
- **HISTORICAL**: imports authorised CSV data with `symbol,timestamp,open,high,low,close,volume` columns; daily CSV candles are cached in SQLite.
- **ZERODHA**: a Kite Connect SDK adapter is available but disabled unless an authenticated client and verified instrument-token mapping are supplied. No credentials are stored or requested.

The market-data cache uses duplicate-safe `(symbol, timeframe, timestamp, source)` keys. NSE market status uses Asia/Kolkata time, 09:15–15:30 regular equity hours, weekend detection, and configurable holidays. The included instrument master deliberately contains no fabricated instrument tokens; extend it only with authorised master data.

## Strategy engine (Phase 4)

`strategy/` provides EMA 9/21/50/200, RSI, MACD, ATR, VWAP, Bollinger Bands, volume analysis, crossover detection, multi-symbol scanning, ATR/fixed risk levels and trailing-stop math. The primary EMA crossover strategy only evaluates a true current-candle crossover; it never treats an already-separated EMA pair as a fresh signal.

Each generated paper signal contains the market-data source, candle timestamp, indicator evidence, rule-agreement score, suggested ATR/fixed stop and target. Scores represent technical-rule agreement only, not probability, investment advice, or expected profitability. Strategy configuration and generated signals persist in SQLite with a uniqueness key that prevents duplicate signals for the same strategy, symbol and candle.

## Historical backtesting (Phase 5)

Open **Backtesting** in the sidebar and provide an authorised historical CSV path. The CSV must contain:

```text
symbol,timestamp,open,high,low,close,volume
RELIANCE,2026-01-05T09:15:00+05:30,1400,1410,1395,1405,250000
```

The included CSV provider accepts daily (`1d`) candles. The backtester refuses simulated candles, runs only against imported historical data, evaluates strategy conditions from completed prior bars, and executes eligible entries on the next bar open. Stop/target gaps, intraday close-out, position allocation, user-entered brokerage/slippage assumptions, gross P&L, charges and net P&L are stored for every completed run.

Default transaction rates are zero by design: rates are date-effective and users must enter the assumptions appropriate to their study. Results are labelled historical simulation, are not forecasts, and do not imply future performance.

## Zerodha Kite Connect (Phase 7)

The broker module uses the official Kite Connect Python SDK but works with no broker credentials. Copy `.env.example` to a server-local `.env` or configure server environment variables: `KITE_API_KEY`, `KITE_API_SECRET`, and a unique `ORBIT_TOKEN_ENCRYPTION_KEY`. Never put these values in Streamlit UI fields or commit `.env`.

The supported flow is: obtain the official `login_url()`, complete the user-directed Zerodha login at the registered redirect URL, pass the returned `request_token` to `complete_login()`, then use the encrypted-at-rest session to fetch account metadata. Kite access tokens are session-bound and need reauthentication after expiry. Live order placement, modification, and cancellation are hard-disabled in Phase 7; connecting a broker never changes the paper-trading mode.

## Live-trading readiness (Phase 8)

The Live Trading view is a monitoring and dry-run control center only. It can read authorised broker metadata through the existing adapter, score broker/database/market/risk/emergency-stop preflight checks, and persist hypothetical order intents marked **DRY RUN — NOT SENT TO BROKER**. The emergency stop pauses only application-generated dry-run intents; it does not cancel, modify, create, or manage broker orders or positions.

Before any future execution deployment, verify server environment configuration, credential protection, encrypted-token key rotation, database backup and recovery, broker reconciliation, market-data freshness, risk controls, audit-log retention, network resilience, and an independent security review.

## Test

```powershell
pytest -q
```

`BrokerAdapter` remains intentionally disconnected. A future Zerodha adapter must implement the provider boundary and must not bypass the paper-trading risk/order services.
