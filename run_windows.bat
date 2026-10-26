@echo off
REM One-click runner for Windows. Double-click, or run from a terminal with options:
REM   run_windows.bat --indices "NIFTY 50" "NIFTY 500"
cd /d "%~dp0"
set "PY=python"
where py >nul 2>nul && set "PY=py -3"
if not exist .venv (
  echo Creating virtual environment, first run only...
  %PY% -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
python run.py %*
echo.
pause
