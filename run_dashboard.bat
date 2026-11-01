@echo off
rem Starts the Superstore RFM dashboard on http://localhost:8501
rem Runs from the project root so .streamlit/config.toml (theme) is picked up, same as on Streamlit Cloud
cd /d "%~dp0"
python -m streamlit run dashboard/app.py
pause
