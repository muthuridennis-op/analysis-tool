import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from supabase import create_client

# 1. Page Configuration for Touch Layout and App Theme
st.set_page_config(page_title="Core Algo Hub", page_icon="📈", layout="centered")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

st.title("📱 Quantitative Trading Terminal")

# 2. Add an Interactive Tab Interface for cleaner navigation
tab_signals, tab_analytics = st.tabs(["📥 Active Signals", "📊 Historical Journal"])

# ==========================================
# TAB 1: ACTIVE SIGNALS ENGINE
# ==========================================
with tab_signals:
    response = supabase.table("signals").select("*").eq("status", "PENDING").execute()
    signals = response.data
    
    if not signals:
        st.success("🟢 All systems nominal. No pending signals detected.")
    else:
        st.warning(f"🚨 Attention: {len(signals)} Trade Action(s) Required")
        
        for sig in signals:
            ticker = sig['ticker']
            direction = sig['direction']
            alert_price = sig['execution_price']
            
            # Draw an isolated visual container for each card
            with st.container(border=True):
                # Layout structure splits the card row into data and quick details
                col_title, col_metric = st.columns([2, 1])
                with col_title:
                    st.markdown(f"### 💱 Asset: `{ticker}`")
                    color = "green" if direction == "BUY" else "red"
                    st.markdown(f"Action Request: :{color}[**{direction}**]")
                with col_metric:
                    st.metric(label="Cloud Trigger", value=f"\${alert_price:.2f}")
                
                # --- INTERACTIVE CHARTING AREA ---
                # Expandable drop-down element so charts only load on command
                with st.expander("🔍 View Live Technical Analysis Chart", expanded=False):
                    st.write("Fetching chart layers...")
                    # Download recent data dynamically to your phone via yfinance
                    raw_df = yf.download(ticker, period="6mo", interval="1d")
                    if not raw_df.empty:
                        if isinstance(raw_df.columns, pd.MultiIndex):
                            raw_df.columns = raw_df.columns.get_level_values(0)
                        raw_df.columns = raw_df.columns.str.lower()
                        
                        # Calculate moving averages on the fly for your visual inspection
                        raw_df['sma_50'] = raw_df['close'].rolling(window=50).mean()
                        raw_df['sma_200'] = raw_df['close'].rolling(window=200).mean()
                        
                        # Construct a rich, touch-interactive Plotly chart canvas
                        fig = go.Figure()
                        # Base Candlestick representation layer
                        fig.add_trace(go.Candlestick(
                            x=raw_df.index, open=raw_df['open'], high=raw_df['high'],
                            low=raw_df['low'], close=raw_df['close'], name="Market Price"
                        ))
                        # Line graphs mapping out your moving average components
                        fig.add_trace(go.Scatter(x=raw_df.index, y=raw_df['sma_50'], line=dict(color='orange', width=1.5), name="SMA 50"))
                        fig.add_trace(go.Scatter(x=raw_df.index, y=raw_df['sma_200'], line=dict(color='blue', width=1.5), name="SMA 200"))
                        
                        # Format parameters optimized specifically for vertical phone viewport boxes
                        fig.update_layout(
                            margin=dict(l=10, r=10, t=10, b=10),
                            height=300,
                            xaxis_rangeslider_visible=False,
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.error("Unable to draw interactive canvas. Tick feed unavailable.")
                
                # --- RESPONSE INTERFACES ---
                btn_left, btn_right = st.columns(2)
                with btn_left:
                    if st.button("✅ Log as Traded", key=f"tr_{sig['id']}", use_container_width=True):
                        supabase.table("signals").update({"status": "MANUALLY_TRADED"}).eq("id", sig['id']).execute()
                        st.toast(f"Logged {ticker} placement.")
                        st.rerun()
                with btn_right:
                    if st.button("❌ Dismiss Alert", key=f"ds_{sig['id']}", use_container_width=True):
                        supabase.table("signals").update({"status": "DISMISSED"}).eq("id", sig['id']).execute()
                        st.rerun()

# ==========================================
# TAB 2: ANALYTICS & LOGGING HISTORICAL JOURNAL
# ==========================================
with tab_analytics:
    st.subheader("📁 Complete Execution Analytics")
    
    # Extract historical logs out of Supabase data structures
    history_res = supabase.table("signals").select("*").neq("status", "PENDING").order("created_at", descending=True).execute()
    history_data = history_res.data
    
    if not history_data:
        st.info("No recorded historical trade data available in this account session.")
    else:
        # Convert JSON table structures directly into native DataFrames
        hist_df = pd.DataFrame(history_data)
        
        # 1. Top-Level Summary Metrics Bar Layout
        total_signals = len(hist_df)
        traded_count = len(hist_df[hist_df['status'] == 'MANUALLY_TRADED'])
        dismiss_count = len(hist_df[hist_df['status'] == 'DISMISSED'])
        acceptance_rate = (traded_count / total_signals * 100) if total_signals > 0 else 0
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Scanned", total_signals)
        col_m2.metric("Executed", traded_count)
        col_m3.metric("Action Rate", f"{acceptance_rate:.1f}%")
        
        # 2. Interactive Graphical Analysis Breakdown
        st.markdown("### 📊 Distribution of Signals")
        status_counts = hist_df['status'].value_counts()
        
        fig_pie = go.Figure(data=[go.Pie(
            labels=status_counts.index, 
            values=status_counts.values, 
            hole=.4,
            marker=dict(colors=['#2ca02c', '#d62728', '#7f7f7f'])
        )])
        fig_pie.update_layout(height=250, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)
        
        # 3. Clean Interactive Tabular Ledger view
        st.markdown("### 📝 Full Audit Log Table")
        st.dataframe(
            hist_df[['ticker', 'direction', 'execution_price', 'status']], 
            use_container_width=True
        )
