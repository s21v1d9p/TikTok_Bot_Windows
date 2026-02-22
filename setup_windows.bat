@echo off
REM ─────────────────────────────────────────────
REM  TikTok Browser Bot – One-Click Windows Setup
REM  Run this file first to install everything
REM ─────────────────────────────────────────────

title TikTok Bot Setup
cd /d "%~dp0"

echo.
echo ==================================================
echo    TikTok Browser Bot - Windows Setup
echo ==================================================
echo.
echo This script will:
echo   1. Create a Python virtual environment
echo   2. Install all required dependencies
echo   3. Download the stealth browser (Chromium)
echo.
echo Please wait, this may take a few minutes...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo [Step 1/4] Creating virtual environment...
if exist "venv" (
    echo Virtual environment already exists, skipping...
) else (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created.
)

echo.
echo [Step 2/4] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)
echo Virtual environment activated.

echo.
echo [Step 3/4] Installing dependencies...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo Dependencies installed.

echo.
echo [Step 4/4] Downloading stealth browser (Chromium)...
playwright install chromium
if errorlevel 1 (
    echo [WARNING] Browser installation failed. Trying with deps...
    playwright install chromium --with-deps
    if errorlevel 1 (
        echo [ERROR] Failed to download browser.
        echo Try running: playwright install chromium
        pause
        exit /b 1
    )
)
echo Browser downloaded.

echo.
echo ==================================================
echo    Setup Complete!
echo ==================================================
echo.
echo Next steps:
echo   1. Double-click run_bot.bat to start the bot
echo   2. On first run, choose option [2] to log in
echo   3. After login, use option [1] for automation
echo.
echo See README.md and INSTALL.md for more details.
echo.
pause
