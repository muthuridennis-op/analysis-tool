@echo off
echo 📈 Initializing S&P 500 Automated Trading Terminal...
cd /d "%~dp0"

if not exist .env (
    echo 🚨 CRITICAL ERROR: .env configuration file not found in project root!
    echo Please create it before running this terminal.
    pause
    exit /b
)

echo 🔌 Launching Streamlit Frontend Dashboard UI...
streamlit run dashboard.py

pause