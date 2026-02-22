# TikTok Browser Bot - Windows Installation Guide

This guide provides step-by-step instructions for setting up and running the TikTok Browser Bot on Windows.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation Steps](#installation-steps)
3. [First-Time Setup](#first-time-setup)
4. [Running the Bot](#running-the-bot)
5. [Configuration](#configuration)
6. [Unattended Mode Setup](#unattended-mode-setup)

---

## Prerequisites

Before installing the bot, ensure your Windows system meets these requirements:

| Requirement | Minimum Version | How to Check |
|-------------|-----------------|--------------|
| Windows | Windows 10 (64-bit) | Press `Win + R`, type `winver` |
| Python | Python 3.10 or higher | Open CMD, type `python --version` |
| RAM | 4 GB minimum | Task Manager → Performance |
| Disk Space | 2 GB free | File Explorer → This PC |
| Internet | Stable connection | - |

### Installing Python on Windows

If Python is not installed:

1. Download Python from [python.org/downloads](https://www.python.org/downloads/)
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH" during installation
4. Click "Install Now"
5. Verify installation:
   ```cmd
   python --version
   pip --version
   ```

---

## Installation Steps

### Step 1: Extract the Bot Package

1. Extract the provided ZIP file to a folder of your choice (e.g., `C:\TikTokBot`)
2. Avoid paths with spaces (don't use `C:\Program Files\TikTokBot`)

### Step 2: Open Command Prompt

1. Press `Win + R`
2. Type `cmd` and press Enter
3. Navigate to the bot folder:
   ```cmd
   cd C:\TikTokBot
   ```

### Step 3: Create Virtual Environment

```cmd
python -m venv venv
```

### Step 4: Activate Virtual Environment

```cmd
venv\Scripts\activate
```

You should see `(venv)` at the beginning of your command prompt.

### Step 5: Install Dependencies

```cmd
pip install -r requirements.txt
```

This will install all required packages including:
- `phantomwright` - Anti-detection browser automation
- `playwright` - Browser automation framework
- Other dependencies listed in `requirements.txt`

### Step 6: Install Playwright Browsers

```cmd
playwright install chromium
```

This downloads the patched Chromium browser used for automation.

---

## First-Time Setup

### Step 1: Initial Login

Run the bot for the first time to set up your TikTok session:

```cmd
python main.py
```

Select option **[2] Re-do manual login (overwrite session)**

### Step 2: Scan QR Code

1. A browser window will open
2. Open TikTok on your phone
3. Go to **Settings → QR Code**
4. Scan the QR code displayed in the browser
5. Wait for login confirmation

### Step 3: Verify Session

After successful login:
1. The bot will save your session to `auth.json`
2. You can now use option **[1] Start automation** for future runs

---

## Running the Bot

### Using the Interactive Menu

```cmd
venv\Scripts\activate
python main.py
```

Available options:
- **[1]** Start automation (auto-login + scheduled loop)
- **[2]** Re-do manual login (overwrite session)
- **[3]** Upload a video now
- **[4]** Schedule a video for later
- **[5]** View scheduled videos
- **[6]** Exit

### Using Batch Files (Recommended for Unattended Mode)

We provide batch files for easy operation:

| File | Purpose |
|------|---------|
| `run_bot.bat` | Start the bot with auto-login |
| `run_bot_silent.bat` | Run minimized (for scheduled tasks) |

Simply double-click the batch file to run.

---

## Configuration

### Main Configuration File: `config.py`

Edit this file to customize bot behavior:

#### Safety Limits (per session)
```python
MAX_FOLLOWS_PER_SESSION = 8    # Max follows per 2-hour cycle
MAX_LIKES_PER_SESSION = 20     # Max likes per cycle
MAX_VIDEOS_TO_WATCH = 7        # Videos to watch in feed
```

#### Sleep Schedule (24-hour format)
```python
SLEEP_START = 22  # 10:00 PM - Bot stops actions
SLEEP_END = 7     # 7:00 AM - Bot resumes actions
```

#### Target Niche
```python
TARGET_HASHTAG = "trading"  # Primary hashtag for profile discovery
```

#### CAPTCHA Settings
```python
DEBUG_CAPTCHA_CAPTURE = True  # Save screenshots when CAPTCHA detected
```

### Video Schedule File: `video_schedule.json`

This file stores scheduled video uploads. Edit manually or use option [4] in the menu.

---

## Unattended Mode Setup

### Option 1: Windows Task Scheduler

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Basic Task**
3. Name: "TikTok Bot"
4. Trigger: **Daily** (or your preferred schedule)
5. Time: Choose start time (e.g., 8:00 AM)
6. Action: **Start a program**
7. Program: `C:\TikTokBot\run_bot_silent.bat`
8. Start in: `C:\TikTokBot`
9. Finish

### Option 2: Windows Startup

1. Press `Win + R`, type `shell:startup`
2. Create a shortcut to `run_bot_silent.bat`
3. Paste the shortcut in the Startup folder
4. The bot will start automatically when Windows boots

### Important Notes for Unattended Mode

1. **Disable Sleep Mode**: 
   - Go to **Settings → System → Power & Sleep**
   - Set "When plugged in, PC goes to sleep after" to **Never**

2. **Disable Windows Update Restart**:
   - Go to **Settings → Update & Security → Windows Update**
   - Click **Advanced Options**
   - Disable "Restart this device as soon as possible"

3. **Stable Internet Connection**:
   - Use wired connection if possible
   - Consider a UPS for power backup

4. **Log Monitoring**:
   - Check `bot.log` regularly for errors
   - CAPTCHA screenshots are saved in `debug/` folder

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.

---

## File Structure

```
TikTokBot/
├── main.py              # Entry point
├── tiktok_bot.py        # Main bot class
├── config.py            # Configuration settings
├── stealth.py           # Anti-detection module
├── bot_utils.py         # Utility functions
├── captcha_solver.py    # CAPTCHA handling
├── auth.json            # Saved session (created after login)
├── bot.log              # Runtime logs
├── requirements.txt     # Python dependencies
├── run_bot.bat          # Windows batch file
├── run_bot_silent.bat   # Silent mode batch file
├── browser_data/        # Browser profile data
├── chrome_profile/      # Persistent browser profile
└── debug/               # CAPTCHA screenshots
```

---

## Support

For issues or questions:
1. Check `bot.log` for error messages
2. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. Check the `debug/` folder for CAPTCHA screenshots
