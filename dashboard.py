import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from supabase import create_client

# Page Configuration optimized for clean touch grids on mobile screens
st.set_page_config(page_title="Algo Dashboard", page_icon="📈", layout="centered")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

st.title("📱 Quantitative Trading Terminal")

# Interactive Multi-Tab Mobile Framework
tab_signals, tab_analytics = st.tabs(["📥 Active Signals", "📊 Historical Journal"])

# ==========================================
# TAB 1: ACTIVE SIGNALS INTERFACE
# ==========================================
with tab_signals:
    try:
        response = supabase.table("signals").select("*").eq("status", "PENDING").execute()
        signals = response.data
    except Exception as e:
        st.error(f"Database Query Error: {e}")
        signals = []
    
    if not signals:
        st.success("🟢 All systems nominal. No pending signals detected.")
    else:
        st.warning(f"🚨 Attention: {len(signals)} Trade Action(s) Required")
        
        for sig in signals:
            ticker = sig['ticker']
            direction = sig['direction']
            alert_price = float(sig['execution_price'])
            stop_loss = float(sig.get('stop_loss', 0.0))
            take_profit = float(sig.get('take_profit', 0.0))
            
            with st.container(border=True):
                col_title, col_m1, col_m2, col_m3 = st.columns(4)
                with col_title:
                    st.markdown(f"### 💱 `{ticker}`")
                    color = "green" if direction == "BUY" else "red"
                    st.markdown(f"Action: :{color}[**{direction}**]")
                with col_m1:
                    st.metric(label="Entry", value=f"\${alert_price:.4f}")
                with col_m2:
                    st.metric(label="🛡️ Stop Loss", value=f"\${stop_loss:.4f}" if stop_loss else "N/A")
                with col_m3:
                    st.metric(label="🎯 Take Profit", value=f"\${take_profit:.4f}" if take_profit else "N/A")
                
                # --- INTERACTIVE CANDLESTICK CHART EXPANDER ---
                with st.expander("🔍 View Live Technical Analysis Chart", expanded=False):
                    st.write("Loading technical chart grid...")
                    raw_df = yf.download(ticker, period="6mo", interval="1d")
                    if not raw_df.empty:
                        if isinstance(raw_df.columns, pd.MultiIndex):
                            raw_df.columns = raw_df.columns.get_level_values(0)
                        raw_df.columns = raw_df.columns.str.lower()
                        
                        # Generate Simple Moving Average lines dynamically on demand
                        raw_df['sma_50'] = raw_df['close'].rolling(window=50).mean()
                        raw_df['sma_200'] = raw_df['close'].rolling(window=200).mean()
                        
                        # Construct a rich, responsive interactive graphical element
                        fig = go.Figure()
                        fig.add_trace(go.Candlestick(
                            x=raw_df.index, open=raw_df['open'], high=raw_df['high'],
                            low=raw_df['low'], close=raw_df['close'], name="Price Action"
                        ))
                        fig.add_trace(go.Scatter(x=raw_df.index, y=raw_df['sma_50'], line=dict(color='orange', width=1.5), name="SMA 50"))
                        fig.add_trace(go.Scatter(x=raw_df.index, y=raw_df['sma_200'], line=dict(color='blue', width=1.5), name="SMA 200"))
                        
                        fig.update_layout(
                            margin=dict(l=10, r=10, t=10, b=10),
                            height=300,
                            xaxis_rangeslider_visible=False,
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.error("Live chart feed currently unavailable.")
                
                # --- RESPONSE MANAGEMENT INTERFACES ---
                btn_left, btn_right = st.columns(2)
                with btn_left:
                    if st.button("✅ Log as Traded", key=f"tr_{sig['id']}", use_container_width=True):
                        supabase.table("signals").update({"status": "MANUALLY_TRADED"}).eq("id", sig['id']).execute()
                        st.toast(f"Logged {ticker} placement.")
                        st.rerun()
                with btn_right:
                    if st.button("❌ Dismiss Alert", key=f"ds_{sig['id']}", use_container_width=True):
                        supabase.table("signals").update({"status": "DISMISSED"}).eq("id", sig['id']).execute()
                        st.toast("Signal cleared.")
                        st.rerun()

# ==========================================
# TAB 2: HISTORICAL TRADING JOURNAL
# ==========================================
with tab_analytics:
    st.subheader("📁 Strategy Historical Log")
    
    try:
        history_res = supabase.table("signals").select("*").neq("status", "PENDING").order("created_at", desc=True).execute()
        history_data = history_res.data
    except Exception as e:
        st.error(f"Error fetching logs: {e}")
        history_data = []
        
    if not history_data:
        st.info("No recorded historical data available.")
    else:
        hist_df = pd.DataFrame(history_data)
        
        # Summary Analytics Layout Cards
        total_signals = len(hist_df)
        traded_count = len(hist_df[hist_df['status'] == 'MANUALLY_TRADED'])
        acceptance_rate = (traded_count / total_signals * 100) if total_signals > 0 else 0
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Scans Logged", total_signals)
        col_m2.metric("Executed", traded_count)
        col_m3.metric("Action Rate", f"{acceptance_rate:.1f}%")
        
        # Distribution Pie Chart
        st.markdown("### 📊 System Activity Breakdown")
        status_counts = hist_df['status'].value_counts()
        fig_pie = go.Figure(data=[go.Pie(
            labels=status_counts.index, 
            values=status_counts.values, 
            hole=.4,
            marker=dict(colors=['#2ca02c', '#d62728', '#7f7f7f'])
        )])
        fig_pie.update_layout(height=250, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)
        
        # Complete Historical Data Table
        st.markdown("### 📝 Full Audit History Ledger")
        st.dataframe(
            hist_df[['ticker', 'direction', 'execution_price', 'status']], 
            use_container_width=True
        )
