import streamlit as st
import os
from supabase import create_client

st.set_page_config(page_title="System Diagnostics", layout="centered")
st.title("⚙️ Database Connection Diagnostics")

# 1. Test Secret Variables extraction
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    st.success("✅ Streamlit successfully extracted keys from the Secrets panel!")
    # Show the first few characters to verify it's the service_role, not the anon key
    st.info(f"Key starts with: `{key[:15]}...` (Verify this matches your service_role string)")
except Exception as e:
    st.error(f"❌ Failed to extract secrets: {e}")
    st.stop()

# 2. Test Connection Initialization
try:
    supabase = create_client(url, key)
    st.success("✅ Supabase client initialized in Python memory successfully.")
except Exception as e:
    st.error(f"❌ Failed to initialize Supabase client: {e}")
    st.stop()

# 3. Test Raw API Request with a Try/Catch Block to capture the hidden error
st.markdown("### 🔍 Initiating Direct Connection Test...")
try:
    # Run a simple query to fetch anything from the table
    response = supabase.table("signals").select("id").limit(1).execute()
    st.success("🎉 CONGRATULATIONS! Connection verified. The table is accessible!")
    st.write("Database Response Data:", response.data)
except Exception as e:
    st.error("❌ The Database rejected the request.")
    st.markdown("#### Here is the real unredacted error message from Supabase:")
    st.code(str(e))
    
    st.markdown("""
    ### 🛠️ Next Steps Based on the Error Above:
    * If the error says **"Invalid API key"** or **"JWTRefused"**: Your `SUPABASE_KEY` string inside Streamlit secrets is missing characters. Re-copy the **service_role** key carefully.
    * If the error says **"relation public.signals does not exist"**: Go to your Supabase dashboard and double-check your table name. Ensure it is exactly all lowercase `signals` plural.
    """)
