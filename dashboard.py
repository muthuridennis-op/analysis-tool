import streamlit as st
from supabase import create_client

# Force the page to render cleanly on mobile screens
st.set_page_config(page_title="Algo Signal Hub", page_icon="📡", layout="centered")

st.title("📡 Algo Signal Desk")
st.subheader("Manual Trading Alerts")

# Initialize connection to your secure database
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]  # Your service_role key
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    st.error("🔒 Database credentials missing. Please check your Streamlit Secrets panel.")
    st.stop()

# Pull any active signals awaiting your manual action
try:
    response = supabase.table("signals").select("*").eq("status", "PENDING").execute()
    signals = response.data
except Exception as e:
    st.error(f"Error connecting to database: {e}")
    signals = []

if not signals:
    st.success("🟢 No pending signals. Systems clear.")
else:
    st.write(f"📥 Found **{len(signals)}** unexecuted cloud setup(s):")
    
    # Loop through each trade signal and build a custom touch UI card
    for sig in signals:
        with st.container():
            st.markdown("---")
            
            # Highlight BUY in green, SELL in red
            color = "green" if sig['direction'].upper() == "BUY" else "red"
            st.markdown(f"### 📊 Asset: **{sig['ticker']}**")
            st.markdown(f"Direction: :{color}[**{sig['direction']}**] | Cloud Alert Price: **${sig['execution_price']:.2f}**")
            st.caption(f"Generated at: {sig.get('created_at', 'Recent')}")
            
            # Responsive mobile action buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("👍 Log as Traded", key=f"app_{sig['id']}", use_container_width=True):
                    # Simply flag it as manually accepted in your database log
                    supabase.table("signals").update({"status": "MANUALLY_TRADED"}).eq("id", sig['id']).execute()
                    st.toast("✅ Logged! Now open your broker app to enter the trade.")
                    st.rerun()
            with col2:
                if st.button("👎 Dismiss Setup", key=f"rej_{sig['id']}", use_container_width=True):
                    supabase.table("signals").update({"status": "DISMISSED"}).eq("id", sig['id']).execute()
                    st.toast("🗑️ Signal hidden.")
                    st.rerun()
