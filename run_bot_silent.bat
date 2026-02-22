@echo off
REM ─────────────────────────────────────────────
REM  TikTok Browser Bot – Silent Mode Launcher
REM  For Windows Task Scheduler / Unattended Mode
REM  Runs minimized with no console window
REM ─────────────────────────────────────────────

cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the bot with auto-login (echo "1" to auto-select option 1)
echo 1 | python main.py >> bot.log 2>&1
