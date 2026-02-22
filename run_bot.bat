@echo off
REM ─────────────────────────────────────────────
REM  TikTok Browser Bot – Windows Quick Launcher
REM  Double-click this file to start the bot.
REM ─────────────────────────────────────────────

title TikTok Browser Bot
cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo.
echo ==========================================
echo   TikTok Browser Bot – Starting ...
echo ==========================================
echo.

python main.py

echo.
echo Bot has exited. Press any key to close.
pause >nul
