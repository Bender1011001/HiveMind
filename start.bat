@echo off
echo Starting Multi-Agent System...
echo ==========================

:: Activate virtual environment
call venv\Scripts\activate
if errorlevel 1 (
    echo Failed to activate virtual environment!
    echo Please run install.bat first.
    pause
    exit /b 1
)

:: Start the application with streamlit
streamlit run run.py
if errorlevel 1 (
    echo Failed to start the application!
    pause
    exit /b 1
)

pause
