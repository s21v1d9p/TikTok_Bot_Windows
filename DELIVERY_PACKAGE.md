# TikTok Browser Bot - Delivery Package

**Delivery Date**: February 16, 2026
**Target Platform**: Windows 10/11 (64-bit)
**Niche**: Trading (Forex / Crypto / Stocks)

---

## Package Contents

### Core Application Files

| File | Description |
|------|-------------|
| `main.py` | Entry point - run this to start the bot |
| `tiktok_bot.py` | Main bot class with all automation logic |
| `config.py` | Configuration settings (limits, niche, delays) |
| `stealth.py` | Anti-detection layer (mouse, fingerprints, CAPTCHA detection) |
| `bot_utils.py` | Helper functions (delays, typing, logging) |
| `captcha_solver.py` | Automatic CAPTCHA solving (rotation + jigsaw) |
| `requirements.txt` | Python dependencies |

### Windows Batch Files

| File | Description |
|------|-------------|
| `setup_windows.bat` | **ONE-CLICK SETUP** - Run this first |
| `run_bot.bat` | **ONE-CLICK LAUNCHER** - Run this after setup |
| `run_bot_silent.bat` | Silent mode for Task Scheduler |

### Documentation

| File | Description |
|------|-------------|
| `README.md` | Main documentation (features, usage, troubleshooting) |
| `INSTALL.md` | Detailed Windows installation guide |
| `TROUBLESHOOTING.md` | Common issues and solutions |
| `CONFIG_GUIDE.md` | Configuration options explained |
| `DELIVERY_PACKAGE.md` | This file - package summary |

### Runtime Files (Created Automatically)

| File | Description |
|------|-------------|
| `auth.json` | Saved login session (created after first login) |
| `bot.log` | Activity log file |
| `video_schedule.json` | Scheduled video uploads |
| `browser_data/` | Browser profile data |
| `chrome_profile/` | Persistent browser profile |
| `debug/` | CAPTCHA screenshots (if issues occur) |

---

## Quick Start Guide

### Step 1: Install Python

1. Download Python 3.10+ from https://www.python.org/downloads/
2. **IMPORTANT**: Check "Add Python to PATH" during installation
3. Click "Install Now"

### Step 2: Run Setup

1. Extract this ZIP file to a folder (e.g., `C:\TikTokBot`)
2. Double-click `setup_windows.bat`
3. Wait for setup to complete (2-5 minutes)

### Step 3: First Login

1. Double-click `run_bot.bat`
2. Select option **[2] Re-do manual login**
3. Scan the QR code with your TikTok app
4. Wait for login confirmation

### Step 4: Run Automation

1. Double-click `run_bot.bat`
2. Select option **[1] Start automation**
3. The bot will run in ~2 hour cycles
4. Press `Ctrl+C` to stop

---

## Configuration Summary

### Current Settings (config.py)

| Setting | Value | Description |
|---------|-------|-------------|
| `TARGET_HASHTAG` | `"trading"` | Primary hashtag for profile discovery |
| `MAX_FOLLOWS_PER_SESSION` | 8 | Max follows per 2-hour cycle |
| `MAX_LIKES_PER_SESSION` | 20 | Max likes per cycle |
| `MAX_VIDEOS_TO_WATCH` | 7 | Videos to watch per cycle |
| `SLEEP_START` | 22 (10 PM) | Hour to stop activity |
| `SLEEP_END` | 7 (7 AM) | Hour to resume activity |

### To Change the Niche

Edit `config.py` and update:
- `TARGET_HASHTAG` - Your primary hashtag
- `FALLBACK_HASHTAGS` - Related hashtags
- `NICHE_KEYWORDS` - Keywords for profile relevance

See `CONFIG_GUIDE.md` for detailed instructions.

---

## Unattended Mode Setup

### Option 1: Windows Task Scheduler

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Basic Task**
3. Name: "TikTok Bot"
4. Trigger: **Daily**
5. Time: Choose start time
6. Action: **Start a program**
7. Program: `C:\TikTokBot\run_bot_silent.bat`
8. Start in: `C:\TikTokBot`

### Option 2: Windows Startup

1. Press `Win + R`, type `shell:startup`
2. Create shortcut to `run_bot_silent.bat`
3. Paste in Startup folder

### Important for Unattended Mode

1. **Disable Sleep**: Settings > System > Power > "When plugged in, PC goes to sleep after" = **Never**
2. **Disable Windows Update Restart**: Settings > Update & Security > Windows Update > Advanced Options > Pause updates
3. **Stable Internet**: Use wired connection if possible

---

## CAPTCHA Handling

The bot includes multiple CAPTCHA countermeasures:

1. **Detection**: Shadow DOM traversal, dialog detection, element matching
2. **Auto-Solve**: Attempts to solve rotation and jigsaw CAPTCHAs
3. **Dismiss**: Tries to close CAPTCHA dialogs
4. **Backoff**: Increases delays when CAPTCHA detected
5. **Logging**: Saves screenshots to `debug/` folder

If CAPTCHA appears frequently:
- Reduce `MAX_FOLLOWS_PER_SESSION` to 2-3
- Increase delays in `config.py`
- Wait 24-48 hours before resuming

---

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| "Python not recognized" | Reinstall Python with "Add to PATH" checked |
| "No module named..." | Run `venv\Scripts\activate` then `pip install -r requirements.txt` |
| "Browser doesn't open" | Run `playwright install chromium` |
| "Auto-login failed" | Use option [2] to re-login |
| CAPTCHA appears often | Reduce limits, increase delays, wait 24-48h |
| Bot stops overnight | Normal - sleep schedule is 10 PM - 7 AM |

See `TROUBLESHOOTING.md` for detailed solutions.

---

## File Structure

```
C:\TikTokBot\
|-- main.py                 # Entry point
|-- tiktok_bot.py           # Main bot logic
|-- config.py               # Configuration
|-- stealth.py              # Anti-detection
|-- bot_utils.py            # Utilities
|-- captcha_solver.py       # CAPTCHA handling
|-- requirements.txt        # Dependencies
|-- setup_windows.bat       # One-click setup
|-- run_bot.bat             # One-click launcher
|-- run_bot_silent.bat      # Silent mode
|-- README.md               # Main docs
|-- INSTALL.md              # Install guide
|-- TROUBLESHOOTING.md      # Troubleshooting
|-- CONFIG_GUIDE.md         # Config reference
|-- DELIVERY_PACKAGE.md     # This file
|-- auth.json               # Session (created after login)
|-- bot.log                 # Activity log
|-- video_schedule.json     # Scheduled videos
|-- venv/                   # Virtual environment
|-- browser_data/           # Browser data
|-- chrome_profile/         # Browser profile
|-- debug/                  # CAPTCHA screenshots
```

---

## Support Checklist

Before reporting issues, check:

1. [ ] Python 3.10+ installed with PATH
2. [ ] `setup_windows.bat` completed successfully
3. [ ] Login completed (option [2])
4. [ ] `bot.log` checked for errors
5. [ ] `debug/` folder checked for CAPTCHA screenshots
6. [ ] Internet connection stable
7. [ ] Sleep mode disabled for unattended use

---

## Version Information

- **Bot Version**: 1.0.0
- **Python Required**: 3.10+
- **Browser**: Phantomwright (patched Chromium)
- **Target OS**: Windows 10/11 (64-bit)

---

## Safety Notes

- The bot uses **no private APIs** - all actions go through TikTok web interface
- Session limits are conservative to reduce account flag risk
- Sleep kill-switch ensures zero activity during night hours
- Adaptive throttling automatically slows on suspicious signals
- All actions include randomized delays for human-like behavior

---

## Disclaimer

This tool is provided for educational purposes. Use it responsibly and in compliance with TikTok's Terms of Service. The authors are not responsible for any account restrictions that may result from automated activity.