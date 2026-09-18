# app.py
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import os
from supabase import create_client
from dotenv import load_dotenv

# --- INITIALIZE ENVIRONMENT VARIABLES ---
load_dotenv()  # Safely injects parameters from your local .env file

# Page Config
st.set_page_config(
    page_title="Algo Dashboard", 
    page_icon="📈", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

@st.cache_resource
def init_supabase():
    # Prioritizes cloud secrets; drops back to local .env configuration automatically
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        st.error("🚨 CRITICAL ERROR: Supabase connection credentials missing from environment.")
        st.stop()
        
    return create_client(url, key)

supabase = init_supabase()

st.title("📱 Trading Terminal")

# --- SIDEBAR: CALCULATOR ---
with st.sidebar:
    st.header("🧮 Lot Size Calculator")
    balance = st.number_input("Balance (\$)", min_value=100.0, value=10000.0, step=500.0)
    risk_pct = st.slider("Risk (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    
    st.divider()
    asset_class = st.radio("Asset Class", ["Forex", "Indices/Commodities"])
    risk_cash = balance * (risk_pct / 100.0)
    
    if asset_class == "Forex":
        pip_stop = st.number_input("Stop (Pips)", min_value=1.0, value=30.0, step=1.0)
        pos_size = risk_cash / (pip_stop * 10.0) if pip_stop > 0 else 0.0
        st.metric("Volume", f"{pos_size:.2f} Lots")
    else:
        point_stop = st.number_input("Stop (\$ Amount)", min_value=0.01, value=5.0, step=0.5)
        units = risk_cash / point_stop if point_stop > 0 else 0.0
        st.metric("Order Size", f"{units:.2f} Units")
    st.caption(f"Max Risk: \${risk_cash:.2f}")

# --- FILTER SEARCH ---
friendly_names = {
    "All Assets": "🌍 All Assets Matrix",
    "EURUSD=X": "🇪🇺 EURUSD (Euro)",
    "GBPUSD=X": "🇬🇧 GBPUSD (Pound)",
    "AUDUSD=X": "🇦🇺 AUDUSD (Aussie)",
    "USDJPY=X": "🇯🇵 USDJPY (Yen)",
    "USDCAD=X": "🇨🇦 USDCAD (Loonie)",
    "^GSPC": "🇺🇸 S&P 500 Index",
    "GC=F": "👑 GC=F (Gold)",
    "CL=F": "🛢️ CL=F (Crude Oil)",
    "BZ=F": "🔥 BZ=F (Brent Oil)"
}

search_selection = st.selectbox(
    "🔍 Filter Terminal Dashboard by Asset Symbol:",
    options=list(friendly_names.keys()),
    format_func=lambda x: friendly_names[x]
)

tab_signals, tab_analytics = st.tabs(["📥 Active Signals", "📊 Historical Journal"])

# ==========================================
# TAB 1: ACTIVE SIGNALS
# ==========================================
with tab_signals:
    try:
        query = supabase.table("signals").select("*").eq("status", "PENDING")
        if search_selection != "All Assets":
            query = query.eq("ticker", search_selection)
        response = query.execute()
        signals = response.data
    except Exception as e:
        st.error(f"DB Error: {e}")
        signals = []
    
    if not signals:
        st.success("🟢 No pending alerts.")
    else:
        st.info(f"⚡ {len(signals)} Active Trade Event(s)")
        
        for sig in signals:
            ticker = sig['ticker']
            direction = sig['direction']
            tf_label = sig.get('timeframe', '1D') 
            alert_price = float(sig['execution_price'])
            sl = float(sig.get('stop_loss', 0.0))
            tp = float(sig.get('take_profit', 0.0))
            
            with st.container(border=True):
                col_title, col_m1, col_m2, col_m3 = st.columns([1.2, 1, 1, 1])
                with col_title:
                    st.markdown(f"### `{ticker}`")
                    color = "green" if direction == "BUY" else "red"
                    st.markdown(f"**{tf_label}** | :{color}[**{direction}**]")
                with col_m1:
                    st.metric("Entry", f"\${alert_price:.4f}")
                with col_m2:
                    st.metric("Stop Loss", f"\${sl:.4f}" if sl else "N/A")
                with col_m3:
                    st.metric("Take Profit", f"\${tp:.4f}" if tp else "N/A")
                
                with st.expander("🔍 Live Chart"):
                    yf_interval = "1d" if tf_label.lower() == "1d" else "4h"
                    yf_period = "6mo" if yf_interval == "1d" else "60d"
                    df = yf.download(ticker, period=yf_period, interval=yf_interval)
                    
                    if not df.empty:
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        df.columns = df.columns.str.lower()
                        
                        df['s50'] = df['close'].rolling(50).mean()
                        df['s200'] = df['close'].rolling(200).mean()
                        
                        fig = go.Figure()
                        fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'], low=df['low'], close=df['close'], name="Price"))
                        fig.add_trace(go.Scatter(x=df.index, y=df['s50'], line=dict(color='#ff9900', width=1.5), name="SMA 50"))
                        fig.add_trace(go.Scatter(x=df.index, y=df['s200'], line=dict(color='#0066cc', width=1.5), name="SMA 200"))
                        fig.update_layout(template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10), height=250, xaxis_rangeslider_visible=False)
                        st.plotly_chart(fig, use_container_width=True)
                
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("✅ Trade", key=f"tr_{sig['id']}", use_container_width=True):
                        supabase.table("signals").update({"status": "MANUALLY_TRADED"}).eq("id", sig['id']).execute()
                        st.rerun()
                with b2:
                    if st.button("❌ Dismiss", key=f"ds_{sig['id']}", use_container_width=True):
                        supabase.table("signals").update({"status": "DISMISSED"}).eq("id", sig['id']).execute()
                        st.rerun()

# ==========================================
# TAB 2: HISTORICAL JOURNAL
# ==========================================
with tab_analytics:
    st.subheader(f"📁 Logs: {friendly_names[search_selection]}")
    try:
        hist_query = supabase.table("signals").select("*").neq("status", "PENDING")
        if search_selection != "All Assets":
            hist_query = hist_query.eq("ticker", search_selection)
        history_res = hist_query.order("created_at", desc=True).execute()
        history_data = history_res.data
    except Exception as e:
        st.error(f"Error: {e}")
        history_data = []
        
    if not history_data:
        st.info("No records found.")
    else:
        hist_df = pd.DataFrame(history_data)
        if 'timeframe' not in hist_df.columns:
            hist_df['timeframe'] = '1D'
            
        total = len(hist_df)
        traded = len(hist_df[hist_df['status'] == 'MANUALLY_TRADED'])
        rate = (traded / total * 100) if total > 0 else 0
        
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Scans Logged", f"{total:,}")
        col_m2.metric("Executed", f"{traded:,}")
        col_m3.metric("Action Rate", f"{rate:.1f}%")
        
        col_chart, col_ledger = st.columns([1, 1.2])
        with col_chart:
            st.markdown("### 📊 Distribution")
            counts = hist_df['status'].value_counts()
            cmap = {'MANUALLY_TRADED': '#2ca02c', 'DISMISSED': '#d62728'}
            ccolors = [cmap.get(n, '#7f7f7f') for n in counts.index]
            
            fig_pie = go.Figure(data=[go.Pie(labels=counts.index, values=counts.values, hole=.5, marker=dict(colors=ccolors))])
            fig_pie.update_layout(height=220, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", x=0, y=-0.1))
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_ledger:
            st.markdown("### 📝 Full Audit Ledger")
            display_df = hist_df[['ticker', 'timeframe', 'direction', 'status']].copy()
            display_df.columns = ['Asset Ticker', 'Timeframe', 'Direction', 'Status Resolution']
            st.dataframe(display_df, use_container_width=True, height=220)
