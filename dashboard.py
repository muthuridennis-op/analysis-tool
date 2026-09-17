import streamlit as st
from supabase import create_client

# Force the page to render cleanly on mobile screens
st.set_page_config(page_title="Algo Dashboard", layout="centered")

st.title("📱 Strategy Signal Control")
st.subheader("Live FXPesa Order Desk")

# Initialize connection to your secure database
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]  # Ensure this is your service_role key
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception:
    st.error("🔒 Database credentials missing. Please check your Streamlit Secrets panel.")
    st.stop()

# Pull any active signals awaiting your approval
try:
    response = supabase.table("signals").select("*").eq("status", "PENDING").execute()
    signals = response.data
except Exception as e:
    st.error(f"Error connecting to database: {e}")
    signals = []

if not signals:
    st.success("🟢 No pending signals. System resting.")
else:
    st.write(f"📥 Found **{len(signals)}** signal(s) requiring authorization:")
    
    # Loop through each trade signal and build a custom touch UI card
    for sig in signals:
        with st.container():
            st.markdown("---")
            
            # Highlight BUY in green, SELL in red
            color = "green" if sig['direction'].upper() == "BUY" else "red"
            st.markdown(f"### 📊 Ticker: **{sig['ticker']}**")
            st.markdown(f"Action: :{color}[**{sig['direction']}**] | Entry Target: **${sig['execution_price']:.2f}**")
            
            # Responsive mobile action buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve Trade", key=f"app_{sig['id']}", use_container_width=True):
                    supabase.table("signals").update({"status": "APPROVED"}).eq("id", sig['id']).execute()
                    st.toast("🚀 Signal Approved! Sending to execution gate...")
                    st.rerun()
            with col2:
                if st.button("❌ Reject", key=f"rej_{sig['id']}", use_container_width=True):
                    supabase.table("signals").update({"status": "REJECTED"}).eq("id", sig['id']).execute()
                    st.toast("🗑️ Signal discarded.")
                    st.rerun()
