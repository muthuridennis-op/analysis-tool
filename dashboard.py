# dashboard.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="S&P 500 Algo Dashboard",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)


@st.cache_resource
def init_supabase():
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except Exception:
        url = None
        key = None

    url = url or os.environ.get("SUPABASE_URL")
    key = key or os.environ.get("SUPABASE_KEY")

    if not url or not key:
        st.error("🚨 CRITICAL ERROR: Supabase credentials missing.")
        st.stop()

    return create_client(url, key)


supabase = init_supabase()

st.title("📈 S&P 500 Trading Terminal")

# --- SIDEBAR: CALCULATOR (manual override) ---
with st.sidebar:
    st.header("🧮 Position Size Calculator")
    st.caption("Manual override — signals carry their own suggested size.")
    balance = st.number_input("Balance ($)", min_value=100.0, value=10000.0, step=500.0)
    risk_pct = st.slider("Risk (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    risk_cash = balance * (risk_pct / 100.0)

    st.divider()
    st.markdown("**S&P 500 / SPY / ES**")
    point_stop = st.number_input(
        "Stop Distance ($ per unit)",
        min_value=0.01, value=5.0, step=0.5,
        help="For SPY: 1 point = $1. For ES futures: 1 point = $50."
    )
    instrument = st.radio("Instrument", ["SPY (Shares)", "ES (Futures)"])
    multiplier = 1.0 if instrument.startswith("SPY") else 50.0

    units = risk_cash / (point_stop * multiplier) if point_stop > 0 else 0.0
    st.metric("Order Size", f"{units:.2f} {instrument.split()[0]}")
    st.caption(f"Max Risk: ${risk_cash:.2f}")

st.divider()

tab_signals, tab_analytics = st.tabs(["📥 Active Signals", "📊 Historical Journal"])

# ==========================================
# TAB 1: ACTIVE SIGNALS
# ==========================================
with tab_signals:
    try:
        response = supabase.table("signals") \
            .select("*") \
            .eq("status", "PENDING") \
            .execute()
        signals = response.data
    except Exception as e:
        st.error(f"DB Error: {e}")
        signals = []

    if not signals:
        st.success("🟢 No pending S&P 500 alerts.")
    else:
        st.info(f"⚡ {len(signals)} Active Signal(s)")

        for sig in signals:
            ticker = sig['ticker']
            direction = sig['direction']
            tf_label = sig.get('timeframe', '1D')
            alert_price = float(sig['execution_price'])
            sl = float(sig.get('stop_loss', 0.0))
            tp = float(sig.get('take_profit', 0.0))

            risk = abs(alert_price - sl) if sl else 0
            reward = abs(tp - alert_price) if tp else 0
            rr = (reward / risk) if risk > 0 else 0

            # Sizing fields (may be None for signals created before the migration)
            size_units = sig.get("size_units")
            size_instrument = sig.get("size_instrument")
            risk_cash = sig.get("risk_cash")

            with st.container(border=True):
                col_title, col_m1, col_m2, col_m3 = st.columns([1.2, 1, 1, 1])
                with col_title:
                    st.markdown(f"### `{ticker}`")
                    color = "green" if direction == "BUY" else "red"
                    st.markdown(f"**{tf_label}** | :{color}[**{direction}**]")
                    st.caption(f"R:R ≈ 1:{rr:.2f}")
                with col_m1:
                    st.metric("Entry", f"${alert_price:.2f}")
                with col_m2:
                    st.metric("Stop Loss", f"${sl:.2f}" if sl else "N/A")
                with col_m3:
                    st.metric("Take Profit", f"${tp:.2f}" if tp else "N/A")

                # Suggested size from scanner
                if size_units:
                    st.caption(
                        f"📐 Suggested: **{size_units:g} {size_instrument}** "
                        f"(risk ≈ ${risk_cash:.2f})"
                    )

                with st.expander("🔍 Live Chart (6mo Daily + Weekly Trend)"):
                    df = yf.download(ticker, period="1y", interval="1d", progress=False)

                    if not df.empty:
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        df.columns = df.columns.str.lower()

                        # Limit display to last 6 months
                        display_df = df.tail(130).copy()
                        display_df['s50'] = df['close'].rolling(50).mean().tail(130)
                        display_df['s200'] = df['close'].rolling(200).mean().tail(130)

                        fig = go.Figure()
                        fig.add_trace(go.Candlestick(
                            x=display_df.index,
                            open=display_df['open'], high=display_df['high'],
                            low=display_df['low'], close=display_df['close'],
                            name="Price"
                        ))
                        fig.add_trace(go.Scatter(
                            x=display_df.index, y=display_df['s50'],
                            line=dict(color='#ff9900', width=1.5), name="SMA 50"
                        ))
                        fig.add_trace(go.Scatter(
                            x=display_df.index, y=display_df['s200'],
                            line=dict(color='#0066cc', width=1.5), name="SMA 200"
                        ))
                        fig.add_hline(y=sl, line_dash="dot", line_color="red",
                                      annotation_text="SL")
                        fig.add_hline(y=tp, line_dash="dot", line_color="green",
                                      annotation_text="TP")
                        fig.update_layout(
                            template="plotly_dark",
                            margin=dict(l=10, r=10, t=10, b=10),
                            height=280,
                            xaxis_rangeslider_visible=False
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        # --- Weekly MTF mini-panel ---
                        try:
                            weekly_df = df.resample('W-FRI').agg({
                                'open': 'first', 'high': 'max',
                                'low': 'min', 'close': 'last', 'volume': 'sum'
                            }).dropna()
                            if len(weekly_df) >= 30:
                                w_sma = weekly_df['close'].rolling(30).mean()
                                last_close = weekly_df['close'].iloc[-1]
                                last_sma = w_sma.iloc[-1]
                                trend = "🟢 Bullish" if last_close > last_sma else "🔴 Bearish"
                                st.caption(
                                    f"**Weekly MTF:** {trend} "
                                    f"(close {last_close:.2f} vs SMA30 {last_sma:.2f})"
                                )
                        except Exception:
                            pass

                b1, b2 = st.columns(2)
                with b1:
                    if st.button("✅ Trade", key=f"tr_{sig['id']}", use_container_width=True):
                        supabase.table("signals").update(
                            {"status": "MANUALLY_TRADED"}
                        ).eq("id", sig['id']).execute()
                        st.rerun()
                with b2:
                    if st.button("❌ Dismiss", key=f"ds_{sig['id']}", use_container_width=True):
                        supabase.table("signals").update(
                            {"status": "DISMISSED"}
                        ).eq("id", sig['id']).execute()
                        st.rerun()


# ==========================================
# TAB 2: HISTORICAL JOURNAL
# ==========================================
with tab_analytics:
    st.subheader("📁 S&P 500 Signal Logs")
    try:
        history_res = supabase.table("signals") \
            .select("*") \
            .neq("status", "PENDING") \
            .order("created_at", desc=True) \
            .execute()
        history_data = history_res.data
    except Exception as e:
        st.error(f"Error: {e}")
        history_data = []

    if not history_data:
        st.info("No records found.")
    else:
        hist_df = pd.DataFrame(history_data)
        if "timeframe" not in hist_df.columns:
            hist_df["timeframe"] = "1D"

        # ------- Outcome stats -------
        total = len(hist_df)
        traded = len(hist_df[hist_df["status"] == "MANUALLY_TRADED"])
        dismissed = len(hist_df[hist_df["status"] == "DISMISSED"])
        tp = len(hist_df[hist_df["status"] == "CLOSED_TP"])
        sl = len(hist_df[hist_df["status"] == "CLOSED_SL"])
        expired = len(hist_df[hist_df["status"] == "CLOSED_TIME"])

        closed = tp + sl + expired
        win_rate = (tp / closed * 100) if closed > 0 else 0.0

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Signals Logged", f"{total:,}")
        col_m2.metric("Executed", f"{traded:,}")
        col_m3.metric("Closed (TP/SL/Time)", f"{closed:,}")
        col_m4.metric("Win Rate", f"{win_rate:.1f}%")

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("🎯 TP Hits", f"{tp}")
        col_b.metric("🛑 SL Hits", f"{sl}")
        col_c.metric("⏱️ Time Exits", f"{expired}")

        # ------- Equity curve -------
        closed_rows = hist_df[
            hist_df["status"].isin(["CLOSED_TP", "CLOSED_SL", "CLOSED_TIME"])
        ].copy()

        if not closed_rows.empty and "exit_price" in closed_rows.columns:
            closed_rows = closed_rows.dropna(subset=["exit_price", "execution_price"])
            if not closed_rows.empty:
                closed_rows["pnl_pct"] = closed_rows.apply(
                    lambda r: ((r["exit_price"] - r["execution_price"])
                               / r["execution_price"] * 100)
                    if r["direction"] == "BUY"
                    else ((r["execution_price"] - r["exit_price"])
                          / r["execution_price"] * 100),
                    axis=1,
                )
                closed_rows = closed_rows.sort_values("created_at")
                closed_rows["equity"] = (1 + closed_rows["pnl_pct"] / 100).cumprod()

                st.markdown("### 📈 Realized Equity Curve")
                fig_eq = go.Figure()
                fig_eq.add_trace(go.Scatter(
                    x=list(range(1, len(closed_rows) + 1)),
                    y=closed_rows["equity"],
                    mode="lines+markers",
                    line=dict(color="#2ca02c", width=2),
                ))
                fig_eq.update_layout(
                    template="plotly_dark",
                    height=240,
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis_title="Trade #",
                    yaxis_title="Equity (×)",
                )
                st.plotly_chart(fig_eq, use_container_width=True)

        # ------- Pie + ledger -------
        col_chart, col_ledger = st.columns([1, 1.2])
        with col_chart:
            st.markdown("### 📊 Distribution")
            counts = hist_df["status"].value_counts()
            cmap = {
                "MANUALLY_TRADED": "#1f77b4",
                "DISMISSED":       "#7f7f7f",
                "CLOSED_TP":       "#2ca02c",
                "CLOSED_SL":       "#d62728",
                "CLOSED_TIME":     "#ff7f0e",
            }
            ccolors = [cmap.get(n, "#aec7e8") for n in counts.index]

            fig_pie = go.Figure(data=[go.Pie(
                labels=counts.index,
                values=counts.values,
                hole=.5,
                marker=dict(colors=ccolors),
            )])
            fig_pie.update_layout(
                height=220,
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation="h", x=0, y=-0.1),
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_ledger:
            st.markdown("### 📝 Audit Ledger")
            cols = ["ticker", "timeframe", "direction", "status"]
            display_df = hist_df[cols].copy()
            display_df.columns = ["Ticker", "Timeframe", "Direction", "Status"]
            st.dataframe(display_df, use_container_width=True, height=220)