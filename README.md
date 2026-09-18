This is a project for an automated market prediction system

The architecture runs an analytical backend engine alongside a visual frontend application, bound together via a cloud database:
1.Multi-Source Data Ingestion: The engine (run_backtest.py) reads a watchlist containing Forex, Indices, and Commodities. It uses a resilient broker array logic within RobustDataProvider that prioritizes low-latency institutional nodes (Alpaca or Interactive Brokers) and drops back to standard Yahoo Finance scraping if the primary links time out.
2.Strategy Evaluation Layer: Data is parsed into standard NumPy arrays and checked across vector formulas inside strategies.py. The system uses a safe_shift method to prevent look-ahead bias (ensuring older values don't roll over to active indices).
3.Volatility Risk Calculations & Deduplication: When a signal conditions trip, the script evaluates the 14-period Average True Range (ATR) to dynamically position stop losses and profit targets based on volatility configurations. It verifies against the database that this isn't a duplicate entry before uploading the record to Supabase.
4Human Interaction Node: The Streamlit dashboard (app.py) updates to display incoming PENDING events. The user can look over visual indicators, run lot calculations based on capital rules, and choose to execute the asset manually on an external platform.
B. Core Tool Stack & Dependencies
1.The project uses a structured data stack running on a lightweight Alpine container:Visual Web Interfaces: streamlit builds the web shell; plotly maps dark-themed candlestick data plots dynamically.
2.Math Engines: Wrapper dependencies for standard C-compiled ta-lib metrics handle analytical tracking array operations.
3.Broker Channels: alpaca-py, ib_insync, and yfinance coordinate cross-network asset extraction tasks.
Backend Database Node: supabase orchestrates secure state-tracking protocols over standard PostgreSQL clusters.
