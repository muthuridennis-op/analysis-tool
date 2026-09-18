@echo off
echo 📈 Initializing Automated Quantitative Trading Terminal...
cd /d "%~dp0"

:: Check if .env file exists before launching
if not exist .env (
    echo 🚨 CRITICAL ERROR: .env configuration file not found in project root!
    echo Please create it before running this terminal layout.
    pause
    exit /b
)

echo 🔌 Launching Streamlit Frontend Dashboard UI...
streamlit run app.py

pause
