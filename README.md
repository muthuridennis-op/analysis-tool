This is a project for an automated market prediction system

.The architecture is;
-A single-asset (S&P 500) mean-reversion trading bot built around the classic RSI(2) dip-buying edge on the S&P 500, wrapped in modern infrastructure:

-Data ingestion → Alpaca (primary) + yfinance (fallback)

-Signal engine → RSI(2) + SMA(200) + VIX + ADX + Weekly MTF gates

-Signal persistence → Supabase (Postgres-as-a-service)

-Human-in-the-loop UI → Streamlit dashboard with charts, position sizing, journal

-Outcome tracker → background job that auto-closes signals on SL/TP/time

-Backtester → same strategies.evaluate_index() used live, replayed historically

-The architecture follows a clean scan → log → review → track pipeline with the scanner never auto-executing trades (it only alerts). That's a deliberate and reasonable design choice for a retail assistant.

.Module-by-Module breakdown;
(1.)config.py-	Single source of truth for thresholds (VIX=18, ADX=20, MTF=30w, R:R=1.5, hold=45d).
(2.)strategies.py-	Pure signal logic. Returns "BUY", "SELL", or None. Reusable by both live and backtest.
(3.)scanner.py- Is the	Orchestrator: fetches data → builds context → calls strategy → dedupes → writes to DB.
(4.)backtester.py-	Replays history bar-by-bar, calls the same strategy function and	Correctly avoids look-ahead by slicing arrays
(5.)data_provider.py-	Alpaca-first with yfinance fallback.
(6.)database.py-	Supabase CRUD wrapper	Thin, fine
(7.)outcome_tracker.py-	Polls open signals, walks forward, closes on SL/TP/age.
(8.)dashboard.py-Streamlit UI: tabs for signals + journal, live charts, position sizer, equity curve.
(9.)logger.py	-Rotating file + console logging	Standard, correct
(10.)start_terminal.bat-	Windows launcher

