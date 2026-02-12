import streamlit as st
import pandas as pd
import altair as alt
import time
import os
import sys
import subprocess

# Ensure src is in python path
sys.path.append(os.getcwd())

from src.main import TradingBot

# Page Config
st.set_page_config(
    page_title="Binance AI Bot",
    page_icon="📈",
    layout="wide"
)

# Custom CSS for aesthetics
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 50px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Bot in Session State (Singleton pattern for Streamlit)
if 'bot' not in st.session_state:
    st.session_state.bot = TradingBot()
    st.session_state.history_df = pd.DataFrame(columns=['timestamp', 'net_worth'])

# Robustness check: Re-init if attributes missing (due to code update)
try:
    _ = st.session_state.bot.paper_session.initial_balance
except AttributeError:
    st.session_state.bot = TradingBot()
    st.session_state.history_df = pd.DataFrame(columns=['timestamp', 'net_worth'])
    st.rerun()

bot = st.session_state.bot

# Sidebar Controls
st.sidebar.title("🤖 Bot Control")

# Mode Indicator
use_testnet = os.getenv('USE_TESTNET', 'True').lower() == 'true'
# Safely check session type using class name to avoid import issues
is_live = type(bot.paper_session).__name__ == 'LiveTradingSession'

if is_live:
    if use_testnet:
        st.sidebar.success("🟢 TESTNET LIVE")
    else:
        st.sidebar.error("🔴 REAL TRADING")
else:
    st.sidebar.info("📝 PAPER TRADING")

# Status Indicator - Render Immediately to avoid flickering
if bot.running:
    status = bot.get_status()
    next_retrain = status.get('next_retrain', 'N/A')
    st.sidebar.success(f"Running...\n\n⏳ Next Auto-Retrain: {next_retrain}")
else:
    st.sidebar.error("Stopped")

col1, col2 = st.sidebar.columns(2)

if col1.button("START", type="primary", disabled=bot.running):
    bot.start()
    st.rerun()

if col2.button("STOP", type="secondary", disabled=not bot.running):
    bot.stop()
    st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🧠 RETRAIN MODEL"):
    # Launch background process
    try:
        subprocess.Popen([sys.executable, "src/agent/retrainer.py"])
        bot.last_retrain_time = time.time() # Reset timer
        st.sidebar.info("🚀 Training started in background!")
        st.sidebar.caption("Takes ~5-10 mins. Bot will auto-reload when done.")
    except Exception as e:
        st.sidebar.error(f"Failed to start training: {e}")



# Main Dashboard
st.title("📈 Binance AI Trading Bot")
st.caption("Dynamic Leverage Mode (-20x to +20x)")

# 1. Real-time Metrics
status = bot.get_status()

# Create metrics row 1
m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric(label="BTC Price", value=f"${status['price']:,.2f}")

with m2:
    balance = status['balance']
    start_bal = bot.paper_session.initial_balance
    delta = balance - start_bal
    st.metric(label="Net Worth (USDT)", value=f"${balance:,.2f}", delta=f"{delta:.2f}")

with m3:
    lev = status['position']
    if abs(lev) < 0.1:
        pos_text = "CASH (0x)"
        st.metric(label="Current Leverage", value=pos_text)
    else:
        direction = "LONG" if lev > 0 else "SHORT"
        st.metric(label="Current Leverage", value=f"{direction} {abs(lev):.2f}x")

with m4:
    win_rate = bot.paper_session.get_win_rate()
    st.metric(label="Win Rate", value=f"{win_rate:.1f}%")

# Create metrics row 2
m5, m6, m7, m8 = st.columns(4)

with m5:
    realized = status['realized_pnl']
    st.metric(label="Realized PnL", value=f"${realized:,.2f}",
              delta=f"{realized:.2f}", delta_color="normal")

with m6:
    unrealized = status['unrealized_pnl']
    st.metric(label="Unrealized PnL", value=f"${unrealized:,.2f}",
              delta=f"{unrealized:.2f}", delta_color="normal")

with m7:
    total_fees = status['total_fees']
    st.metric(label="Total Fees", value=f"${total_fees:,.2f}")

with m8:
    action = status.get('action', '--')
    st.metric(label="Last Target", value=action)

# 2. Charts & Logs
tab1, tab2 = st.tabs(["Price Chart", "Trade History"])

with tab1:
    # Update history for chart (Simulated)
    # In a real app, you'd pull this from bot.history or fetcher
    # Update history for chart
    if bot.running:
        new_row = pd.DataFrame([{'timestamp': pd.Timestamp.now(), 'net_worth': status['balance']}])
        st.session_state.history_df = pd.concat([st.session_state.history_df, new_row], ignore_index=True)
        # Keep last 100 points
        if len(st.session_state.history_df) > 100:
            st.session_state.history_df = st.session_state.history_df.iloc[-100:]
            
    if not st.session_state.history_df.empty:
        df_chart = st.session_state.history_df.copy()
        nw_min = df_chart['net_worth'].min()
        nw_max = df_chart['net_worth'].max()
        padding = max((nw_max - nw_min) * 0.1, 10)
        
        chart = alt.Chart(df_chart).mark_line(
            color='#00cc66',
            strokeWidth=3,
            interpolate='monotone'
        ).encode(
            x=alt.X('timestamp:T', title='Time', axis=alt.Axis(format='%H:%M:%S')),
            y=alt.Y('net_worth:Q', title='Net Worth (USDT)',
                     scale=alt.Scale(domain=[nw_min - padding, nw_max + padding])),
            tooltip=[
                alt.Tooltip('timestamp:T', title='Time', format='%H:%M:%S'),
                alt.Tooltip('net_worth:Q', title='Net Worth', format=',.2f')
            ]
        ).properties(
            height=400
        ).interactive()
        
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Waiting for data...")

with tab2:
    st.write("Recent Trades (Session)")
    # Convert list of dicts to DataFrame
    if bot.paper_session.history:
        df_trades = pd.DataFrame(bot.paper_session.history).iloc[::-1].reset_index(drop=True)
        
        def style_df(styler):
            # Color 'type' text
            def color_type(val):
                if val == 'LONG': return 'color: #00cc66'
                elif val == 'SHORT': return 'color: #ff4444'
                elif val == 'CLOSE': return 'color: #ffaa00'
                return ''
            
            # Color PnL values
            def color_pnl(val):
                if val > 0: return 'color: #00cc66'
                elif val < 0: return 'color: #ff4444'
                return ''
            
            return styler.map(color_type, subset=['type']) \
                         .map(color_pnl, subset=['realized_pnl']) \
                         .map(color_pnl, subset=['unrealized_pnl'])
        
        st.dataframe(style_df(df_trades.style), use_container_width=True)
    else:
        st.text("No trades yet.")

# Auto-refresh logic like a game loop
if bot.running:
    time.sleep(1) # Refresh every 1s
    st.rerun()
