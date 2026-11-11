"""ORBIT ALGO — paper-trading dashboard.

All market-facing values in this demo are simulated.  The SQLite repository and
BrokerAdapter boundary make it safe to replace the sample feed later, without
putting order placement logic in the UI.
"""
from __future__ import annotations

import sqlite3
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select

from backend.database.connection import SessionLocal
from backend.database.models import Order
from backend.services.analytics_service import AnalyticsService
from backend.services.portfolio_service import PortfolioService
from backend.services.position_service import PositionService
from backend.trading.paper_trading import bootstrap_paper_trading
from data.providers.base_provider import DataProviderMode
from data.services.market_data_service import MarketDataService
from strategy.strategy_manager import StrategyManager
from backtesting.costs import TransactionCostConfig
from backtesting.engine import BacktestConfig, HistoricalBacktestEngine
from backtesting.models import BacktestRun
from backtesting.export import trade_ledger_csv
from data.providers.csv_provider import CSVMarketDataProvider
from data.providers.simulated_provider import SimulatedMarketDataProvider
from paper_trading.service import PaperTradingService
from paper_trading.scheduler import PaperTradingScheduler
from paper_trading.worker import scan_active_paper_session
from paper_trading.models import PaperNotification
from broker.zerodha import ZerodhaBrokerService
from broker.exceptions import BrokerError
from readiness.service import ReadinessService
from readiness.models import DryRunOrderIntent, ReadinessAuditLog


st.set_page_config(page_title="SanTom | AI Trading Command Center", page_icon="◈", layout="wide", initial_sidebar_state="expanded")

DB_PATH = Path(__file__).with_name("orbit_algo.db")


class PaperTradingRepository:
    """Small local store for settings; no credentials or live orders are handled."""

    def __init__(self, path: Path):
        self.path = path
        with sqlite3.connect(self.path) as con:
            con.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            con.execute("INSERT OR IGNORE INTO settings VALUES ('paper_trading', '1')")

    def get_paper_mode(self) -> bool:
        with sqlite3.connect(self.path) as con:
            row = con.execute("SELECT value FROM settings WHERE key='paper_trading'").fetchone()
        return row[0] == "1"

    def set_paper_mode(self, enabled: bool) -> None:
        with sqlite3.connect(self.path) as con:
            con.execute("UPDATE settings SET value=? WHERE key='paper_trading'", ("1" if enabled else "0",))


class BrokerAdapter:
    """Future integration seam. It deliberately reports disconnected in this build."""
    name = "Broker integration not configured"
    connected = False


repo = PaperTradingRepository(DB_PATH)
broker = BrokerAdapter()
bootstrap_paper_trading()


def backend_snapshot() -> tuple:
    """Read dashboard state through services; all values remain paper/simulated."""
    session = SessionLocal()
    try:
        analytics, market = AnalyticsService(session), MarketDataService(session, DataProviderMode.SIMULATION)
        return (PortfolioService(session).summary(), PositionService(session).list(), analytics.performance(), market.scanner(), analytics.strategies(), analytics.signals(), market.health(), StrategyManager(session).get_or_create())
    finally:
        session.close()


def money(value: float) -> str:
    return f"₹{value:,.0f}"


def pnl(value: float) -> str:
    return f"+₹{value:,.0f}" if value >= 0 else f"-₹{abs(value):,.0f}"


def tone(value: float) -> str:
    return "gain" if value >= 0 else "loss"


def sample_scanner(quotes) -> pd.DataFrame:
    rows = []
    for quote in quotes:
        rsi = round(50 + quote.change_percent * 9, 1)
        trend = "Bullish" if quote.change_percent > .18 else "Bearish" if quote.change_percent < -.18 else "Neutral"
        signal = "BUY" if trend == "Bullish" else "SELL" if trend == "Bearish" else "HOLD"
        rows.append([quote.symbol, quote.ltp, quote.change_percent, rsi, trend, f"{quote.volume / 1_000_000:.2f}M", signal])
    return pd.DataFrame(rows, columns=["Symbol", "LTP (₹)", "Change %", "RSI", "EMA trend", "Volume", "Signal"])


def equity_chart(period: str, performance: list[dict]) -> go.Figure:
    points = {"1W": 7, "1M": 30, "3M": 90, "YTD": 180}[period]
    source = performance[-points:]
    dates = pd.to_datetime([item["date"] for item in source])
    values = [item["equity"] for item in source]
    daily_pnl = [item["daily_pnl"] for item in source]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=values, mode="lines", name="Portfolio equity", line=dict(color="#635BFF", width=3), fill="tozeroy", fillcolor="rgba(99,91,255,.08)", hovertemplate="%{x|%d %b}<br><b>₹%{y:,.0f}</b><extra></extra>"))
    fig.add_trace(go.Scatter(x=dates, y=daily_pnl, mode="lines", name="Daily P&L", line=dict(color="#44AF69", width=2, dash="dot"), yaxis="y2", hovertemplate="%{x|%d %b}<br><b>₹%{y:,.0f}</b><extra></extra>"))
    fig.update_layout(height=285, margin=dict(l=0, r=0, t=15, b=0), paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", hovermode="x unified", legend=dict(orientation="h", y=1.12, x=0), xaxis=dict(showgrid=False, zeroline=False, color="#737987"), yaxis=dict(showgrid=True, gridcolor="#EEF0F5", tickprefix="₹", zeroline=False, color="#737987"), yaxis2=dict(overlaying="y", side="right", showgrid=False, tickprefix="₹", zeroline=False, color="#737987"), font=dict(family="Inter, Arial", color="#737987"))
    return fig


def render_backtesting_workspace():
    st.markdown("<div class='card'><div class='card-title'>Historical backtesting <span class='pill'>HISTORICAL ONLY</span></div><div class='muted'>Uses imported CSV OHLCV data and next-bar execution. Results are simulated historical analysis, not a prediction or a live-trading recommendation.</div>", unsafe_allow_html=True)
    path_col, symbol_col, range_col = st.columns([1.5, 1, 1])
    csv_path = path_col.text_input("Historical CSV path", placeholder="C:\\data\\reliance_daily.csv", key="backtest_csv")
    symbols = symbol_col.multiselect("Symbols", ["RELIANCE", "HDFCBANK", "INFY", "TCS", "ICICIBANK", "SBIN", "TATAMOTORS"], default=["RELIANCE"], key="backtest_symbols")
    timeframe = range_col.selectbox("Timeframe", ["1d", "1h", "30m", "15m", "5m", "1m"], key="backtest_timeframe")
    setting_a, setting_b, setting_c, setting_d = st.columns(4)
    initial_capital = setting_a.number_input("Initial capital", min_value=1000.0, value=100000.0, step=1000.0)
    allocation = setting_b.slider("Capital allocation %", 1, 100, 20)
    brokerage = setting_c.number_input("Brokerage % assumption", min_value=0.0, value=0.0, step=0.01)
    slippage = setting_d.number_input("Slippage % assumption", min_value=0.0, value=0.0, step=0.01)
    st.caption("CSV columns required: symbol, timestamp (timezone-aware ISO 8601), open, high, low, close, volume. Imported CSV mode currently accepts daily candles; choose 1d for this source.")
    if st.button("Run historical backtest", type="primary"):
        if not csv_path:
            st.error("Historical data is required. Enter an authorised CSV path before running a backtest.")
        elif timeframe != "1d":
            st.error("The CSV provider currently imports daily candles only. Select 1d or add an authorised intraday provider.")
        elif not symbols:
            st.error("Select at least one symbol.")
        else:
            try:
                provider = CSVMarketDataProvider(csv_path)
                by_symbol = {symbol: provider.candles(symbol, "1d", datetime(2000, 1, 1).astimezone(), datetime(2100, 1, 1).astimezone()) for symbol in symbols}
                session = SessionLocal()
                try:
                    config = StrategyManager(session).get_or_create()
                    costs = TransactionCostConfig(brokerage_pct=brokerage, slippage_pct=slippage)
                    result = HistoricalBacktestEngine(session, config, costs).run(by_symbol, BacktestConfig(symbols, timeframe, initial_capital, allocation), "HISTORICAL")
                    session.commit(); st.session_state["backtest_result"] = result
                finally: session.close()
                st.success("Historical backtest completed. Execution uses the next available bar and the displayed assumptions.")
            except Exception as error:
                st.error(f"Backtest could not run: {error}")
    result = st.session_state.get("backtest_result")
    if result:
        metrics = result["metrics"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Final capital", money(metrics["final_capital"]), f"{metrics['return_pct']:+.2f}%")
        m2.metric("Net P&L", money(metrics["net_pnl"]), f"{metrics['total_trades']} trades")
        m3.metric("Maximum drawdown", f"{metrics['max_drawdown']:.2f}%")
        m4.metric("Transaction costs", money(metrics["transaction_costs"]))
        curve = pd.DataFrame(result["equity"])
        if not curve.empty:
            fig = go.Figure(go.Scatter(x=curve["timestamp"], y=curve["equity"], mode="lines", line=dict(color="#635BFF", width=3), fill="tozeroy", fillcolor="rgba(99,91,255,.08)")); fig.update_layout(title="Historical equity curve", height=260, paper_bgcolor="white", plot_bgcolor="white", margin=dict(l=0,r=0,t=35,b=0))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        ledger = pd.DataFrame(result["trades"])
        if ledger.empty: st.info("No qualifying trades were generated for this range and configuration. Metrics requiring trades are intentionally unavailable.")
        else:
            st.dataframe(ledger, use_container_width=True, hide_index=True)
            st.download_button("Export trade ledger CSV", trade_ledger_csv(result["trades"]), "orbit_algo_backtest_trades.csv", "text/csv")
    session = SessionLocal()
    try:
        history = session.query(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(10).all()
        if history:
            st.markdown("<div class='card-title'>Previous backtests</div>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([[run.id, run.strategy_name, run.symbols, run.timeframe, run.initial_capital, run.final_capital, run.data_source, run.created_at] for run in history], columns=["Run", "Strategy", "Symbols", "Timeframe", "Initial capital", "Final capital", "Data source", "Run at"]), use_container_width=True, hide_index=True)
    finally: session.close()
    st.markdown("</div>", unsafe_allow_html=True)


def render_paper_trading_workspace():
    st.markdown("<div class='card'><div class='card-title'>Automated paper trading <span class='pill'>SIMULATED · NO REAL ORDERS</span></div><div class='muted'>Scheduler scans only during NSE regular market hours in IST. It uses labelled simulation data and simulated fills.</div>", unsafe_allow_html=True)
    session = SessionLocal()
    try:
        service = PaperTradingService(session, SimulatedMarketDataProvider()); state = service.dashboard()
        controls = st.columns(4)
        if controls[0].button("Start paper trading", type="primary"):
            service.start(); session.commit(); scheduler = PaperTradingScheduler(scan_active_paper_session, state["state"].interval_seconds); scheduler.start(); st.success("Paper trading scheduler started. It remains idle outside NSE hours.")
        if controls[1].button("Pause / Resume"):
            service.resume() if state["state"].status == "PAUSED" else service.pause(); session.commit(); st.rerun()
        if controls[2].button("Stop paper trading"):
            service.stop(); session.commit(); st.rerun()
        enabled = controls[3].toggle("Kill switch", value=state["control"].kill_switch)
        if enabled != state["control"].kill_switch: state["control"].kill_switch = enabled; session.commit()
        summary = state["summary"]
        a, b, c, d = st.columns(4)
        a.metric("Status", state["state"].status); b.metric("Virtual balance", money(summary.available_balance)); c.metric("Invested capital", money(summary.invested_capital)); d.metric("Today's P&L", pnl(summary.unrealised_pnl))
        e, f, g, h = st.columns(4)
        e.metric("Realised P&L", pnl(summary.realised_pnl)); f.metric("Open positions", len(state["positions"])); g.metric("Total fills", state["total_trades"]); h.metric("Wins / losses", f"{state['winning_trades']} / {state['losing_trades']}")
        st.caption(f"Strategy: {state['state'].strategy_name} · Universe: {state['state'].universe} · Interval: {state['state'].interval_seconds}s · Simulation only")
        if state["positions"]:
            positions = pd.DataFrame([[p.symbol, p.quantity, p.average_entry_price, SimulatedMarketDataProvider().quote(p.symbol).ltp, (SimulatedMarketDataProvider().quote(p.symbol).ltp-p.average_entry_price)*p.quantity] for p in state["positions"]], columns=["Symbol", "Quantity", "Entry", "Current simulated price", "Unrealised P&L"])
            st.dataframe(positions, use_container_width=True, hide_index=True)
        notices = list(session.scalars(select(PaperNotification).order_by(PaperNotification.created_at.desc()).limit(8)))
        if notices:
            st.markdown("<div class='card-title'>Recent paper-trading activity</div>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([[n.created_at, n.level, n.event, n.message] for n in notices], columns=["Time", "Level", "Event", "Details"]), use_container_width=True, hide_index=True)
    finally: session.close()
    st.markdown("</div>", unsafe_allow_html=True)


def render_broker_settings():
    st.markdown("<div class='card'><div class='card-title'>Broker connection <span class='pill'>LIVE EXECUTION LOCKED</span></div><div class='muted'>Zerodha connection can expose account and authorised market data only. It does not enable live order placement.</div>", unsafe_allow_html=True)
    session = SessionLocal()
    try:
        broker = ZerodhaBrokerService(session); connection = broker.connection()
        a, b, c, d = st.columns(4)
        a.metric("Broker", "Zerodha Kite"); b.metric("Status", connection.status); c.metric("Authentication", "Configured" if connection.encrypted_access_token else "Required"); d.metric("Live execution", "Disabled")
        first, second, third = st.columns(3)
        if first.button("Connect Zerodha"):
            try: st.info(f"Open the official login flow: {broker.login_url()}")
            except BrokerError as error: st.warning(str(error))
        if second.button("Test connection"):
            try: broker.sync_account(); session.commit(); st.success("Connection verified. Account metadata refreshed.")
            except BrokerError as error: st.warning(str(error))
        if third.button("Disconnect"):
            broker.disconnect(); session.commit(); st.success("Broker session disconnected. Paper trading remains available.")
        st.caption("Credentials are server environment variables only. API secrets and access tokens are never shown in this interface or written to logs.")
    finally: session.close()
    st.markdown("</div>", unsafe_allow_html=True)


def render_live_readiness():
    st.markdown("<div class='card'><div class='card-title'>Live Trading Control Center <span class='pill'>LIVE TRADING: DISABLED</span></div><div class='muted'>Execution mode: <b>DRY RUN</b>. This screen never submits, modifies, or cancels broker orders.</div>", unsafe_allow_html=True)
    session = SessionLocal()
    try:
        readiness = ReadinessService(session); result = readiness.preflight()
        status, score, mode, broker = st.columns(4)
        status.metric("Live trading", "DISABLED"); score.metric("Readiness score", f"{result['score']}/100"); mode.metric("Execution mode", "DRY RUN"); broker.metric("Broker", readiness.broker.connection().status)
        state = readiness.state(); toggle = st.toggle("Emergency stop — pause dry-run intents", value=state.emergency_stop)
        if toggle != state.emergency_stop: readiness.emergency_stop(toggle); session.commit(); st.rerun()
        st.markdown("<div class='card-title'>Preflight validation</div>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(result["checks"]), use_container_width=True, hide_index=True)
        st.caption("A readiness score is an operational-health summary, not a performance or profitability prediction.")
        intents = list(session.scalars(select(DryRunOrderIntent).order_by(DryRunOrderIntent.created_at.desc()).limit(10)))
        st.markdown("<div class='card-title'>Dry-run order intents</div>", unsafe_allow_html=True)
        if intents: st.dataframe(pd.DataFrame([[x.created_at, x.symbol, x.side, x.quantity, x.entry_price, x.stop_loss, x.target_price, x.estimated_costs, x.status] for x in intents], columns=["Time", "Symbol", "Side", "Quantity", "Hypothetical entry", "Stop", "Target", "Estimated costs", "Status"]), use_container_width=True, hide_index=True)
        else: st.info("No dry-run intents yet. New intents appear only from validated strategy signals and are never sent to the broker.")
        audit = list(session.scalars(select(ReadinessAuditLog).order_by(ReadinessAuditLog.created_at.desc()).limit(8)))
        if audit:
            st.markdown("<div class='card-title'>Readiness audit log</div>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([[x.created_at, x.level, x.event, x.details] for x in audit], columns=["Time", "Level", "Event", "Details"]), use_container_width=True, hide_index=True)
    finally: session.commit(); session.close()
    st.markdown("</div>", unsafe_allow_html=True)


def render_workspace_page(page: str):
    """Consistent non-overview workspace pages backed by the existing services."""
    summary, position_rows, performance_rows, scanner_quotes, strategy_rows, signal_rows, market_health, strategy_config = backend_snapshot()
    st.markdown(f"<div class='eyebrow'>ORBIT ALGO · PAPER MODE</div><div class='page-title'>{page}</div><div class='muted'>Institutional trading workspace · simulated or authorised data is clearly labelled.</div>", unsafe_allow_html=True)
    if page in {"Market Scanner", "Watchlist"}:
        st.markdown("<div class='card'><div class='card-title'>Live Stock Scanner <span class='pill'>SIMULATED</span></div>", unsafe_allow_html=True)
        a,b,c,d = st.columns(4); a.selectbox("Universe", ["NIFTY 50","NIFTY 100","NIFTY 500"], key="page_universe"); b.selectbox("Exchange", ["NSE"], key="page_exchange"); c.selectbox("Signal", ["ALL","BUY","SELL","HOLD"], key="page_signal"); d.selectbox("Timeframe", ["5 Minutes","15 Minutes","1 Day"], key="page_time")
        scanner = sample_scanner(scanner_quotes); st.dataframe(scanner, use_container_width=True, hide_index=True, column_config={"Change %":st.column_config.NumberColumn(format="%+.2f%%")}); st.caption("Quotes are simulated until an authorised data provider is connected.")
        st.markdown("</div>", unsafe_allow_html=True)
    elif page in {"Strategies", "Algo Engine"}:
        left,right = st.columns([1.25,1])
        with left:
            st.markdown("<div class='card'><div class='card-title'>Strategy Library</div>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([[x.name,"Enabled" if x.active else "Paused",f"{x.win_rate:.0f}%",x.trades,f"{x.profit_factor:.2f}"] for x in strategy_rows],columns=["Strategy","Status","Win rate","Signals","Profit factor"]),use_container_width=True,hide_index=True); st.markdown("</div>",unsafe_allow_html=True)
        with right:
            st.markdown(f"<div class='card'><div class='card-title'>EMA crossover configuration</div><p class='muted'>Timeframe: {strategy_config.timeframe} · Minimum score: {strategy_config.min_signal_score}/100</p><p class='muted'>EMA {strategy_config.ema_fast}/{strategy_config.ema_slow} · RSI {strategy_config.rsi_period} · ATR × {strategy_config.atr_multiplier}</p></div>",unsafe_allow_html=True)
    elif page in {"Positions", "Portfolio"}:
        st.markdown("<div class='card'><div class='card-title'>Portfolio positions <span class='pill'>PAPER</span></div>",unsafe_allow_html=True)
        st.metric("Total portfolio value",money(summary.total_value),f"{summary.overall_return_pct:+.2f}%")
        frame=pd.DataFrame([[x.symbol,"BUY" if x.quantity>0 else "SELL",abs(x.quantity),x.average_entry_price,x.current_price,x.unrealised_pnl] for x in position_rows],columns=["Symbol","Side","Quantity","Entry","Current","Unrealised P&L"]); st.dataframe(frame,use_container_width=True,hide_index=True); st.markdown("</div>",unsafe_allow_html=True)
    elif page == "Orders":
        session=SessionLocal()
        try:
            orders=list(session.query(Order).order_by(Order.created_at.desc()).limit(50)); table=pd.DataFrame([[o.id,o.symbol,o.side.value,o.order_type.value,o.quantity,o.filled_quantity,o.status.value,o.average_fill_price,o.created_at] for o in orders],columns=["Order","Symbol","Side","Type","Quantity","Filled","Status","Fill price","Created"])
            st.markdown("<div class='card'><div class='card-title'>Order history <span class='pill'>PAPER</span></div>",unsafe_allow_html=True); st.dataframe(table,use_container_width=True,hide_index=True); st.markdown("</div>",unsafe_allow_html=True)
        finally: session.close()
    elif page == "Analytics":
        st.markdown("<div class='card'><div class='card-title'>Portfolio analytics</div>",unsafe_allow_html=True); st.plotly_chart(equity_chart("1M",performance_rows),use_container_width=True,config={"displayModeBar":False}); st.markdown("</div>",unsafe_allow_html=True)
    elif page == "AI Assistant":
        st.markdown("<div class='card'><div class='card-title'>AI research assistant <span class='pill'>ANALYSIS ONLY</span></div><p class='muted'>This workspace can explain the system’s visible indicators and risk state. It does not make or present trading predictions as real signals.</p>",unsafe_allow_html=True); prompt=st.text_input("Ask about a visible indicator or your paper portfolio",placeholder="e.g. Explain the current simulated portfolio P&L");
        if prompt: st.info("AI research responses are not connected in this local build. Your prompt was not sent to a broker or used to create an order.")
        st.markdown("</div>",unsafe_allow_html=True)
    elif page == "Risk Management":
        st.markdown("<div class='card'><div class='card-title'>Risk utilization</div>",unsafe_allow_html=True); st.metric("Capital utilization",f"{summary.invested_capital/summary.total_capital:.1%}"); st.progress(min(1.0,summary.invested_capital/summary.total_capital)); st.caption("Risk settings persist in SQLite and apply to paper orders."); st.markdown("</div>",unsafe_allow_html=True)
    elif page == "Notifications":
        st.markdown("<div class='card'><div class='card-title'>Notifications</div><p class='muted'>No unacknowledged platform notifications. Broker and market-data status remain visible in the header.</p></div>",unsafe_allow_html=True)
    else:
        st.markdown("<div class='card'><div class='card-title'>Workspace status</div><p class='muted'>This section uses the shared ORBIT design system. Select Market Scanner, Strategies, Portfolio, Orders, Backtesting, Paper Trading, Live Trading, or Settings for its dedicated workspace.</p></div>",unsafe_allow_html=True)


def inject_css() -> None:
    st.markdown("""<style>
    header[data-testid="stHeader"] { background:transparent !important; border:0 !important; } #MainMenu, footer { visibility:hidden; }
    .stApp { background:radial-gradient(circle at 50% -12%,rgba(114,79,255,.22) 0,rgba(24,19,30,.64) 28%,#0b0c12 66%),linear-gradient(130deg,#090a10,#12101a 52%,#0c1010); color:#e9e3db; min-height:100vh; }
    .stApp:before,.stApp:after { content:""; position:fixed; z-index:-1; width:38rem; height:38rem; filter:blur(92px); opacity:.24; pointer-events:none; border-radius:50%; } .stApp:before { background:#6d4dff; top:-20rem; left:22%; } .stApp:after { background:#13c785; bottom:-24rem; right:-9rem; }
    [data-testid='stSidebar'] { background:linear-gradient(180deg,rgba(13,14,20,.90),rgba(8,10,15,.86)) !important; border-right:1px solid rgba(255,255,255,.08); backdrop-filter:blur(24px); } [data-testid='stSidebar'] > div:first-child { padding:1.35rem .8rem; }
    [data-testid='stMetric'] { background:linear-gradient(135deg,rgba(255,255,255,.10),rgba(255,255,255,.035)); border:1px solid rgba(255,255,255,.13); border-radius:18px; padding:16px; box-shadow:inset 0 1px rgba(255,255,255,.11),0 16px 38px rgba(0,0,0,.20); backdrop-filter:blur(20px); transition:transform .28s cubic-bezier(.2,.8,.2,1),border-color .28s,box-shadow .28s; }
    [data-testid='stMetric']:hover { transform:translateY(-4px); border-color:rgba(184,255,77,.46); box-shadow:inset 0 1px rgba(255,255,255,.14),0 20px 44px rgba(0,0,0,.28),0 0 24px rgba(184,255,77,.07); }
    [data-testid='stMetricLabel'] { color:#a29a91; font-size:.7rem; text-transform:uppercase; letter-spacing:.08em; } [data-testid='stMetricValue'] { color:#f3eee8; font-size:1.35rem; }
    .block-container { padding:1.05rem 1.45rem 2.5rem; max-width:1800px; } .orbit-brand { font-size:1.15rem; font-weight:850; letter-spacing:.14em; color:#c7ff71; text-shadow:0 0 18px rgba(184,255,77,.38); } .orbit-sub { font-size:.61rem; letter-spacing:.18em; color:#9791b5; margin-top:4px; }
    .eyebrow { color:#b5a9ff; font-size:.65rem; font-weight:780; letter-spacing:.15em; text-transform:uppercase; } .page-title { font-size:1.58rem; font-weight:720; letter-spacing:-.045em; margin:.18rem 0 0; color:#fbf8f5; }
    .card { background:linear-gradient(135deg,rgba(255,255,255,.09),rgba(255,255,255,.025)); border:1px solid rgba(255,255,255,.12); border-radius:18px; padding:16px; box-shadow:inset 0 1px rgba(255,255,255,.10),0 18px 42px rgba(0,0,0,.16); backdrop-filter:blur(22px); transition:transform .3s cubic-bezier(.2,.8,.2,1),border-color .3s,box-shadow .3s; margin-bottom:12px; }
    .card:hover { transform:translateY(-3px); border-color:rgba(185,167,255,.42); box-shadow:inset 0 1px rgba(255,255,255,.13),0 24px 48px rgba(0,0,0,.21),0 0 26px rgba(115,83,255,.09); }
    .card-title { font-size:.76rem; letter-spacing:.10em; text-transform:uppercase; color:#f0ecf7; font-weight:780; margin-bottom:11px; } .muted { color:#aaa5b8; font-size:.74rem; }
    .value { font-size:1.42rem; font-weight:760; letter-spacing:-.045em; color:#fff; } .gain { color:#baff64; text-shadow:0 0 14px rgba(186,255,100,.25); } .loss { color:#ff717d; text-shadow:0 0 14px rgba(255,113,125,.22); }
    .status-dot { display:inline-block; width:6px; height:6px; border-radius:100%; background:#aafb53; box-shadow:0 0 8px #aafb53; margin-right:6px; } .amber-dot { background:#ffb648; box-shadow:0 0 8px #ffb648; }
    .widget-row { padding:9px 0; border-bottom:1px solid rgba(255,255,255,.07); } .widget-row:last-child { border-bottom:0; } .strategy { padding:10px 0; border-bottom:1px solid rgba(255,255,255,.07); } .strategy:last-child { border-bottom:0; }
    .pill { background:rgba(139,103,255,.20); color:#d5caff; border:1px solid rgba(178,153,255,.40); padding:3px 8px; border-radius:999px; font-size:.61rem; font-weight:800; letter-spacing:.07em; box-shadow:inset 0 1px rgba(255,255,255,.11); }
    div[data-testid='stButton'] > button { border-radius:11px; border-color:rgba(255,255,255,.12); background:rgba(255,255,255,.07); color:#ebe7f2; font-weight:700; font-size:.77rem; transition:all .25s ease; } div[data-testid='stButton'] > button:hover { transform:translateY(-2px); border-color:rgba(185,167,255,.65); color:#fff; background:rgba(134,103,255,.18); box-shadow:0 10px 20px rgba(77,54,171,.18); }
    .stProgress > div > div { background:linear-gradient(90deg,#8f72ff,#c4ff62) !important; border-radius:999px; } .stProgress > div { background:rgba(255,255,255,.10); border-radius:999px; } .stDataFrame { border:1px solid rgba(255,255,255,.12); border-radius:12px; overflow:hidden; } [data-testid='stSidebar'] .stRadio label { color:#bbb6c4 !important; font-size:.77rem; transition:all .2s ease; } [data-testid='stSidebar'] .stRadio label:hover { color:#fff !important; transform:translateX(3px); }
    .terminal-nav { display:flex; gap:7px; align-items:center; padding:10px 12px; background:rgba(255,255,255,.055); border:1px solid rgba(255,255,255,.105); border-radius:16px; backdrop-filter:blur(24px); margin-bottom:15px; box-shadow:inset 0 1px rgba(255,255,255,.10),0 15px 35px rgba(0,0,0,.14); } .terminal-nav .brand { color:#e9e1ff; font-weight:900; letter-spacing:.14em; margin-right:auto; } .terminal-nav span { border:1px solid rgba(255,255,255,.09); background:rgba(10,10,15,.22); color:#bbb5c5; padding:5px 9px; border-radius:999px; font-size:.62rem; letter-spacing:.05em; transition:all .25s ease; } .terminal-nav span:hover { color:#fff; border-color:rgba(184,255,77,.42); transform:translateY(-1px); } .terminal-nav .live { color:#c9ff7b; border-color:rgba(186,255,100,.45); background:rgba(161,245,85,.09); box-shadow:0 0 16px rgba(174,247,84,.10); }
    .stTextInput input, .stSelectbox [data-baseweb="select"] > div { background:rgba(255,255,255,.10) !important; border-color:rgba(255,255,255,.15) !important; color:#f6f2ff !important; border-radius:12px !important; backdrop-filter:blur(16px); } .stTextInput input::placeholder { color:#aaa3b3 !important; }
    /* ORBIT institutional light design system */
    :root { --orbit-bg:#F7F8FA; --orbit-surface:#FFFFFF; --orbit-text:#171923; --orbit-muted:#737987; --orbit-line:#E8EAF0; --orbit-accent:#6257E8; --orbit-accent-soft:#F0EFFF; --orbit-green:#16A36A; --orbit-red:#E05252; --orbit-shadow:0 8px 28px rgba(25,31,49,.06); }
    header[data-testid="stHeader"] { background:rgba(255,255,255,.92)!important; border-bottom:1px solid var(--orbit-line)!important; backdrop-filter:blur(16px); }
    .stApp { background:var(--orbit-bg)!important; color:var(--orbit-text)!important; } .stApp:before,.stApp:after { display:none!important; }
    [data-testid='stSidebar'] { background:#fff!important; border-right:1px solid var(--orbit-line)!important; box-shadow:6px 0 26px rgba(23,25,35,.025); } [data-testid='stSidebar'] > div:first-child { padding:1rem .65rem; }
    .block-container { max-width:1780px; padding:1.05rem 1.45rem 2.5rem; }
    .orbit-brand { color:#171923!important; font-size:1.08rem!important; letter-spacing:-.03em!important; text-shadow:none!important; } .orbit-brand:first-letter { color:var(--orbit-accent); } .orbit-sub { color:#737987!important; font-size:.61rem!important; letter-spacing:.10em!important; }
    .terminal-nav { background:rgba(255,255,255,.88)!important; border:1px solid var(--orbit-line)!important; border-radius:12px!important; box-shadow:0 5px 18px rgba(20,25,42,.035)!important; backdrop-filter:blur(14px); } .terminal-nav .brand { color:#171923!important; } .terminal-nav span { background:#fff!important; border-color:var(--orbit-line)!important; color:#5f6675!important; } .terminal-nav span:hover { color:var(--orbit-accent)!important; border-color:#c9c4ff!important; transform:translateY(-1px); } .terminal-nav .live { color:#fff!important; background:linear-gradient(135deg,#7568ee,#5647d5)!important; border-color:#6257E8!important; box-shadow:0 6px 14px rgba(98,87,232,.20)!important; }
    .eyebrow { color:#6257E8!important; } .page-title { color:#171923!important; font-size:1.52rem!important; }
    [data-testid='stMetric'] { background:#fff!important; border:1px solid var(--orbit-line)!important; border-radius:12px!important; box-shadow:var(--orbit-shadow)!important; backdrop-filter:none!important; } [data-testid='stMetric']:hover { transform:translateY(-2px)!important; border-color:#ccc7fc!important; box-shadow:0 12px 28px rgba(74,65,192,.10)!important; } [data-testid='stMetricLabel'] { color:#737987!important; } [data-testid='stMetricValue'] { color:#171923!important; }
    .card { background:#fff!important; border:1px solid var(--orbit-line)!important; border-radius:12px!important; box-shadow:var(--orbit-shadow)!important; backdrop-filter:none!important; } .card:hover { transform:none!important; border-color:#DFE1E8!important; box-shadow:0 10px 28px rgba(25,31,49,.075)!important; } .card-title { color:#171923!important; letter-spacing:-.01em!important; text-transform:none!important; font-size:.98rem!important; } .muted { color:#737987!important; }
    .value { color:#171923!important; } .gain { color:#16A36A!important; text-shadow:none!important; } .loss { color:#E05252!important; text-shadow:none!important; } .status-dot { background:#16A36A!important; box-shadow:none!important; } .amber-dot { background:#E5A23B!important; box-shadow:none!important; }
    .widget-row,.strategy { border-color:var(--orbit-line)!important; } .pill { background:#F0EFFF!important; color:#6257E8!important; border-color:#dedbff!important; border-radius:6px!important; box-shadow:none!important; }
    div[data-testid='stButton'] > button { background:#fff!important; color:#303544!important; border-color:#DDE0E8!important; border-radius:8px!important; box-shadow:0 2px 5px rgba(23,25,35,.03)!important; } div[data-testid='stButton'] > button:hover { background:#F7F6FF!important; color:#5045D4!important; border-color:#BDB6F8!important; box-shadow:0 6px 14px rgba(98,87,232,.10)!important; }
    .stProgress > div { background:#EEF0F5!important; } .stProgress > div > div { background:#6257E8!important; }
    .stTextInput input, .stSelectbox [data-baseweb="select"] > div { background:#fff!important; border-color:#DDE0E8!important; color:#252936!important; backdrop-filter:none!important; } .stTextInput input::placeholder { color:#969CAB!important; }
    [data-testid='stSidebar'] .stRadio label { color:#343948!important; padding:5px 8px; border-radius:7px; font-size:.78rem; } [data-testid='stSidebar'] .stRadio label:hover { color:#5045D4!important; background:#F6F5FF; transform:none!important; } [data-testid='stSidebar'] .stRadio input:checked + div { background:#6257E8!important; }
    .stDataFrame { border:1px solid var(--orbit-line)!important; border-radius:9px!important; } [data-testid='stDataFrame'] { background:#fff!important; }
    @media(max-width:900px) { .block-container { padding:.75rem!important; } .terminal-nav span:not(.live) { display:none; } .terminal-nav { margin-top:4px; } }
    </style>""", unsafe_allow_html=True)


inject_css()

with st.sidebar:
    st.markdown("<div class='orbit-brand'>◉ &nbsp;ORBIT ALGO</div><div class='orbit-sub'>NSE TRADING INTELLIGENCE</div>", unsafe_allow_html=True)
    st.divider()
    nav = {"⌂  Overview":"Overview", "☆  Watchlist":"Watchlist", "⌕  Market Scanner":"Market Scanner", "☷  Strategies":"Strategies", "<>  Algo Engine":"Algo Engine", "▣  Positions":"Positions", "▤  Orders":"Orders", "▱  Portfolio":"Portfolio", "▧  Backtesting":"Backtesting", "◉  Paper Trading":"Paper Trading", "◌  Live Trading":"Live Trading", "▥  Analytics":"Analytics", "✦  AI Assistant":"AI Assistant", "♢  Risk Management":"Risk Management", "♧  Notifications":"Notifications", "⚙  Settings":"Settings"}
    page = nav[st.radio("Navigation", list(nav), label_visibility="collapsed")]
    st.divider()
    st.markdown("<div class='eyebrow'>System status</div><p class='muted'><span class='status-dot'></span>Algo engine operational</p><p class='muted'><span class='amber-dot status-dot'></span>Market data: simulation</p>", unsafe_allow_html=True)
    st.markdown("<div class='card'><div class='card-title'>Institutional workspace</div><div class='muted'>Paper trades, analytics, and risk controls in one place.</div></div>", unsafe_allow_html=True)
    st.button("View subscription", use_container_width=True)

st.markdown("<div class='terminal-nav'><div class='brand'>ORBIT ALGO</div><span class='live'>⌁ PAPER TRADING</span><span>● Market: Simulated</span><span>Broker: Not connected</span><span>🔔 Notifications</span><span>SS · Sanjai</span></div>", unsafe_allow_html=True)
head_l, head_r = st.columns([3.7, 1.25])
with head_l:
    st.markdown(f"<div class='eyebrow'>PAPER TRADING · {page.upper()} · {datetime.now().strftime('%d %b %Y %H:%M')}</div><div class='page-title'>Trading Overview</div><div class='muted'>Your market intelligence and portfolio performance at a glance.</div>", unsafe_allow_html=True)
with head_r:
    search = st.text_input("Search instruments", placeholder="Search NSE symbol or strategy…", label_visibility="collapsed")

if search:
    st.info(f"Showing paper-market results matching **{search.upper()}**. Live exchange lookup is not enabled.")

bar1, bar2, bar3 = st.columns([1.1, 1.25, 1.25])
with bar1:
    st.markdown("<div class='muted'><span class='status-dot'></span>Market simulation active</div>", unsafe_allow_html=True)
with bar2:
    paper = st.toggle("Paper trading", value=repo.get_paper_mode())
    repo.set_paper_mode(paper)
with bar3:
    st.markdown("<div class='muted'>Broker: <b>Not connected</b> &nbsp; ◌ &nbsp; 2 notifications</div>", unsafe_allow_html=True)

if page != "Overview":
    st.info(f"{page} terminal is connected to the existing paper-trading workspace below. Market values remain explicitly simulated where no authorised live provider is configured.")
    if page == "Backtesting": render_backtesting_workspace()
    elif page == "Paper Trading": render_paper_trading_workspace()
    elif page == "Live Trading": render_live_readiness()
    elif page == "Settings": render_broker_settings()
    else: render_workspace_page(page)
    st.stop()

main, rail = st.columns([3.15, 1.05], gap="large")
summary, position_rows, performance_rows, scanner_quotes, strategy_rows, signal_rows, market_health, strategy_config = backend_snapshot()
with main:
    a, b, c = st.columns(3)
    with a:
        st.metric("Total capital", money(summary.total_value), f"{summary.overall_return_pct:+.2f}% overall")
        st.caption(f"Invested {money(summary.invested_capital)} · Cash {money(summary.available_balance)}")
    with b:
        st.metric("Today's P&L", pnl(summary.unrealised_pnl), f"{summary.daily_return_pct:+.2f}%")
        st.caption("Simulated paper performance")
    with c:
        used = min(1.0, summary.invested_capital / summary.total_capital)
        st.metric("Available margin", money(summary.available_balance), f"{used:.0%} used")
        st.progress(used)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    chart_title, chart_tabs = st.columns([2.3, 1.7])
    with chart_title:
        st.markdown("<div class='card-title'>Portfolio performance</div><div class='muted'>Equity curve and cumulative daily P&L · simulated</div>", unsafe_allow_html=True)
    with chart_tabs:
        period = st.segmented_control("Range", ["1W", "1M", "3M", "YTD"], default="1M", label_visibility="collapsed")
    st.plotly_chart(equity_chart(period or "1M", performance_rows), use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    left, right = st.columns([1.25, 1])
    with left:
        st.markdown("<div class='card'><div class='card-title'>Live stock scanner</div>", unsafe_allow_html=True)
        f1, f2 = st.columns(2)
        universe = f1.selectbox("Universe", ["NIFTY 50", "NIFTY 100", "NIFTY 500"], label_visibility="collapsed")
        signal_filter = f2.selectbox("Signal", ["ALL", "BUY", "SELL", "HOLD"], label_visibility="collapsed")
        scanner = sample_scanner(scanner_quotes)
        if signal_filter != "ALL": scanner = scanner[scanner["Signal"] == signal_filter]
        st.caption(f"{universe} · simulated quotes · click column headers to sort")
        st.dataframe(scanner, use_container_width=True, hide_index=True, height=280, column_config={"Change %": st.column_config.NumberColumn(format="%+.2f%%"), "RSI": st.column_config.NumberColumn(format="%.1f")})
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown("<div class='card'><div class='card-title'>Strategy performance</div>", unsafe_allow_html=True)
        st.caption(f"Rule engine · {strategy_config.timeframe} · minimum agreement score {strategy_config.min_signal_score}/100")
        for item in strategy_rows:
            tag = "Active" if item.active else "Paused"
            st.markdown(f"<div class='strategy'><b>{item.name}</b> <span class='pill'>{tag}</span><br><span class='muted'>Backtest win rate {item.win_rate:.0f}% &nbsp;·&nbsp; {item.trades} trades &nbsp;·&nbsp; PF {item.profit_factor:.2f}</span></div>", unsafe_allow_html=True)
        if st.button("Configure strategies", use_container_width=True):
            st.toast("Strategy configuration is a paper-trading placeholder.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='card'><div class='card-title'>Open positions <span class='pill'>PAPER</span></div><div class='muted'>Prices and unrealised P&L are simulated; no exit action places an order.</div>", unsafe_allow_html=True)
    positions = pd.DataFrame([[p.symbol, "BUY" if p.quantity > 0 else "SELL", abs(p.quantity), p.average_entry_price, p.current_price, p.unrealised_pnl, "—", "—"] for p in position_rows], columns=["Stock", "Side", "Qty", "Entry", "Current", "Unrealised P&L", "Stop loss", "Target"])
    st.dataframe(positions, use_container_width=True, hide_index=True, column_config={"Unrealised P&L": st.column_config.NumberColumn(format="₹%0.2f"), "Entry": st.column_config.NumberColumn(format="₹%0.2f"), "Current": st.column_config.NumberColumn(format="₹%0.2f")})
    st.markdown("</div>", unsafe_allow_html=True)

with rail:
    st.markdown(f"<div class='card'><div class='card-title'>Trading account</div><div class='muted'>Account balance</div><div class='value'>{money(summary.available_balance)}</div><br><div class='muted'>Today's return <b class='gain'>{summary.daily_return_pct:+.2f}%</b></div><div class='muted'>Overall return <b class='gain'>{summary.overall_return_pct:+.2f}%</b></div><div class='muted'>Risk utilisation</div>", unsafe_allow_html=True)
    st.progress(min(1.0, summary.invested_capital / summary.total_capital)); st.caption(f"{summary.invested_capital / summary.total_capital:.0%} of configured capital")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='card'><div class='card-title'>Market overview</div>", unsafe_allow_html=True)
    for label, value, change in [("NIFTY 50", "24,682.20", "+0.42%"), ("NIFTY BANK", "52,101.35", "+0.28%"), ("SENSEX", "80,342.13", "+0.36%"), ("India VIX", "13.42", "-1.18%")]:
        st.markdown(f"<div class='widget-row'><b>{label}</b><br><span class='muted'>{value}</span> <span class='{tone(float(change.replace('%','').replace('+','')))}' style='float:right'>{change}</span></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='card'><div class='card-title'>Active signals</div>", unsafe_allow_html=True)
    for item in signal_rows:
        st.markdown(f"<div class='widget-row'><b>{item.symbol}</b> <span class='pill'>{item.signal}</span><br><span class='muted'>Entry ₹{item.entry_price:,.0f} · Target ₹{item.target_price:,.0f}</span></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='card'><div class='card-title'>System health</div><div class='widget-row'><span class='status-dot'></span>Algo engine <span style='float:right' class='gain'>Healthy</span></div><div class='widget-row'><span class='amber-dot status-dot'></span>Market data <span style='float:right'>{market_health['mode']}</span></div><div class='widget-row'><span class='amber-dot status-dot'></span>Market session <span style='float:right'>{market_health['market_status']}</span></div><div class='widget-row'><span class='amber-dot status-dot'></span>Broker API <span style='float:right'>Disconnected</span></div><p class='muted'>Simulated only · no live connectivity</p></div>", unsafe_allow_html=True)
    st.markdown("<div class='card'><div class='card-title'>Upcoming market events</div><div class='widget-row'><b>Market opening</b><br><span class='muted'>Next trading session · 09:15 IST</span></div><div class='widget-row'><b>Market closing</b><br><span class='muted'>Next trading session · 15:30 IST</span></div><div class='widget-row'><b>Risk review</b><br><span class='muted'>Scheduled · 16:00 IST</span></div></div>", unsafe_allow_html=True)

st.caption("ORBIT ALGO is running in PAPER TRADING mode. Values are simulated and no broker or exchange connection is active.")

if page == "Backtesting":
    render_backtesting_workspace()
if page == "Paper Trading":
    render_paper_trading_workspace()
if page == "Live Trading":
    render_live_readiness()
if page == "Settings":
    render_broker_settings()
