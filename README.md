# TikTok Browser Bot - Trading Niche

A Python automation bot that operates via the TikTok **web interface** using a stealth browser. Designed for the **Trading** niche (Forex / Crypto / Stocks).

---

## Quick Links

| Document | Description |
|----------|-------------|
| [INSTALL.md](INSTALL.md) | **Detailed Windows installation guide** |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | **Common issues and solutions** |
| [config.py](config.py) | Configuration settings |

---

## Features

| Feature | Description |
|---|---|
| **Manual Login (First Run)** | Opens a browser for QR-code / credential login; saves session cookies for future runs |
| **Auto Login** | Loads saved cookies and validates the session automatically |
| **Feed Interaction** | Watches and likes niche-related videos on the For-You page |
| **Mutuals Growth** | Visits `#trading` hashtag pages, finds profiles with mutual connections, and follows them |
| **Fallback Hashtags** | Automatically tries alternative hashtags if the primary yields few results |
| **Suggested Accounts** | Inspects the sidebar for niche-relevant suggested users |
| **Video Upload** | Uploads a video with a human-typed caption |
| **Video Scheduling** | Schedule videos for later upload with a specific date and time |
| **Sleep Kill-Switch** | Pauses all activity between 10 PM - 7 AM local time |
| **Anti-Detection** | Stealth browser, desktop-only user-agents, human-like typing, Bezier mouse paths |
| **Adaptive Throttle** | Automatically slows down or pauses when detecting suspicious signals (CAPTCHA, rate limits) |
| **CAPTCHA Solver** | Attempts to solve rotation and jigsaw CAPTCHAs automatically using image analysis |

---

## Project Structure

```
tiktok_browser_bot/
├── main.py              # Entry point - run this file
├── tiktok_bot.py        # Main TikTokBot class (all automation logic)
├── config.py            # All settings, paths, selectors, niche keywords
├── bot_utils.py         # Helper functions (delays, typing, sleep check)
├── stealth.py           # Anti-detection layer (mouse movement, fingerprints)
├── captcha_solver.py    # Automatic CAPTCHA solving (rotation + jigsaw)
├── requirements.txt     # Python dependencies
├── setup_windows.bat    # ONE-CLICK SETUP - run this first
├── run_bot.bat          # ONE-CLICK LAUNCHER - run this after setup
└── README.md            # This file
```

**Files created at runtime (do NOT delete):**
- `auth.json` - Your saved login session (created after first login)
- `chrome_profile/` - Browser profile data (keeps you logged in)
- `bot.log` - Activity log file
- `video_schedule.json` - Scheduled video uploads
- `debug/` - Debug screenshots (only if CAPTCHA issues occur)

---

## Windows Setup (Step-by-Step)

### Option A: Automatic Setup (Recommended)

1. **Install Python 3.10+** from https://www.python.org/downloads/
   - **IMPORTANT:** During installation, check the box that says **"Add Python to PATH"**
   - Click "Install Now"

2. **Double-click `setup_windows.bat`**
   - This will automatically create the virtual environment, install all dependencies, and download the browser
   - Wait for it to finish (may take 2-5 minutes on first run)
   - You should see "Setup complete!" at the end

3. **Double-click `run_bot.bat`** to start the bot

---

### Option B: Manual Setup

If the automatic setup doesn't work, follow these steps in **Command Prompt** or **PowerShell**:

1. **Install Python 3.10+** from https://www.python.org/downloads/
   - Check **"Add Python to PATH"** during installation

2. **Open Command Prompt** (press `Win + R`, type `cmd`, press Enter)

3. **Navigate to the bot folder:**
   ```
   cd C:\path\to\tiktok_browser_bot
   ```
   (Replace with the actual path where you extracted the files)

4. **Create a virtual environment:**
   ```
   python -m venv venv
   ```

5. **Activate the virtual environment:**
   ```
   venv\Scripts\activate
   ```
   You should see `(venv)` appear at the beginning of your command line.

6. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

7. **Install the stealth browser:**
   ```
   python -m playwright install chromium
   ```

8. **Run the bot:**
   ```
   python main.py
   ```

---

## First Run - Login

On the **very first run**, the bot has no saved session, so it will open a browser window for you to log in manually.

1. Run the bot (double-click `run_bot.bat` or run `python main.py`)
2. A browser window will open showing TikTok's login page
3. **Log in to your TikTok account** (scan QR code with your phone, or use email/password)
4. Wait for the login to be confirmed - the bot will detect it and save your session
5. The bot will close. **Run it again** to start automation.

From now on, the bot will auto-login using your saved session. If the session expires, choose option **[2]** from the menu to re-login.

---

## Daily Usage

After setup and first login, just **double-click `run_bot.bat`** each time you want to run the bot.

You will see this menu:

```
==================================================
   TikTok Browser Bot - Trading Niche
==================================================

Saved session found. What would you like to do?
  [1] Start automation (auto-login + scheduled loop)
  [2] Re-do manual login (overwrite session)
  [3] Upload a video now
  [4] Schedule a video for later
  [5] View scheduled videos
  [6] Exit
Choice (1-6):
```

### Menu Options Explained

| Option | What It Does |
|---|---|
| **1** | Starts the full automation loop. The bot will interact with the feed, find mutual accounts, follow niche users, and check for scheduled uploads. Repeats every ~2 hours. **Press Ctrl+C to stop.** |
| **2** | Opens a browser for you to log in again. Use this if your session expired or you want to switch accounts. |
| **3** | Upload a single video right now. You'll be asked for the video file path and caption. |
| **4** | Schedule a video for later. Enter the file path, caption, and date/time. The bot will upload it automatically when running in automation mode (option 1). |
| **5** | View all scheduled videos and their status (pending, done, failed). |
| **6** | Exit the program. |

---

## How the Automation Works

When you choose option **[1]**, the bot runs a session every ~2 hours:

### Session Flow

1. **Check scheduled uploads** - If any videos are scheduled for now or past-due, upload them first
2. **Feed interaction** - Scroll the For-You page, watch videos, and like niche-relevant content
3. **Mutuals growth** - Visit `#trading` hashtag pages, find profiles with mutual connections AND trading-related content, then follow them
4. **Suggested accounts** - Check the sidebar for niche-relevant suggested users
5. **Wait ~2 hours** - Then repeat

### Mutual Friends Logic (Detail)

1. Navigates to the `#trading` hashtag page (or configured hashtag)
2. Scrolls to load video cards
3. Extracts unique profile links (filters out video links)
4. Visits each profile and checks:
   - **Niche relevance** - Does the bio/username/content contain trading keywords?
   - **Mutual connections** - Does TikTok show "Followed by..." or mutual friend indicators?
5. Only follows users who match BOTH criteria
6. If the primary hashtag yields few profiles, automatically tries fallback hashtags (`forextrading`, `daytrading`, `cryptotrading`, etc.)
7. Respects per-session follow limits to avoid account flags

### Sleep Kill-Switch

The bot will **not perform any actions** between **10 PM and 7 AM** (your local time). If the bot is running during these hours, it will pause and wait until 7 AM to resume. This protects your account from suspicious overnight activity.

---

## Video Upload

### Upload Now (Option 3)

1. Run the bot and choose option **[3]**
2. Enter the **full path** to your video file, for example:
   ```
   C:\Users\YourName\Videos\my_trading_video.mp4
   ```
3. Enter your caption (hashtags included)
4. The bot will log in, navigate to the upload page, and post your video

### Schedule for Later (Option 4)

1. Run the bot and choose option **[4]**
2. Enter the video file path
3. Enter the caption
4. Enter the date and time in this format: `YYYY-MM-DD HH:MM`
   - Example: `2026-03-15 14:30` (March 15, 2026 at 2:30 PM)
5. Start the automation loop (option **[1]**) - the bot will upload the video at the scheduled time

View all scheduled videos with option **[5]**.

---

## Configuration

All settings are in **`config.py`**. Open it with any text editor (Notepad, VS Code, etc.) to adjust.

### Key Settings

| Setting | Default | What It Controls |
|---|---|---|
| `SLEEP_START` | `22` | Hour to stop activity (10 PM, 24-hour format) |
| `SLEEP_END` | `7` | Hour to resume activity (7 AM, 24-hour format) |
| `MAX_FOLLOWS_PER_SESSION` | `8` | Maximum accounts to follow per session |
| `MAX_LIKES_PER_SESSION` | `20` | Maximum videos to like per session |
| `MAX_VIDEOS_TO_WATCH` | `7` | Videos to watch on the feed per session |
| `TARGET_HASHTAG` | `"trading"` | Primary hashtag for finding accounts |
| `FALLBACK_HASHTAGS` | `["forextrading", ...]` | Backup hashtags if primary yields few results |
| `NICHE_KEYWORDS` | `["trading", "forex", ...]` | Keywords used to detect niche-relevant profiles |

### Changing the Niche

To target a different niche (e.g., fitness instead of trading):

1. Open `config.py` in a text editor
2. Change `TARGET_HASHTAG` to your niche hashtag (e.g., `"fitness"`)
3. Update `FALLBACK_HASHTAGS` with related hashtags (e.g., `["workout", "gym", "bodybuilding"]`)
4. Update `NICHE_KEYWORDS` with relevant keywords (e.g., `["fitness", "workout", "gym", "exercise", ...]`)
5. Save the file and restart the bot

### Adjusting Timing

- **Session interval**: The bot runs a session every 110-140 minutes (randomized). This is set in `main.py` line 227.
- **Sleep hours**: Change `SLEEP_START` and `SLEEP_END` in `config.py` (24-hour format).
- **Delays between actions**: Adjust `DELAY_SHORT`, `DELAY_MEDIUM`, `DELAY_LONG` in `config.py`. Longer delays = safer but slower.

---

## Logs

The bot logs all activity to:
- **Console** - You can see what's happening in real-time in the command prompt window
- **`bot.log`** - A file in the bot folder with the full history

If something goes wrong, check `bot.log` for error details.

---

## Troubleshooting

### "Python is not recognized as an internal or external command"

Python is not on your PATH. Either:
- Reinstall Python and check **"Add Python to PATH"** during installation
- Or add Python manually: search "Environment Variables" in Windows, edit PATH, and add `C:\Users\YourName\AppData\Local\Programs\Python\Python3XX\` and its `Scripts\` subfolder

### "No module named ..." error

Dependencies aren't installed. Run:
```
venv\Scripts\activate
pip install -r requirements.txt
```

### Browser doesn't open / Playwright error

The stealth browser isn't installed. Run:
```
venv\Scripts\activate
python -m playwright install chromium
```

### "Auto-login failed" message

Your saved session has expired. Choose option **[2]** to log in again manually.

### Bot gets stuck or CAPTCHA appears frequently

- TikTok may be rate-limiting your account. Stop the bot for a few hours.
- Try increasing the delay values in `config.py` (`DELAY_SHORT`, `DELAY_MEDIUM`, `DELAY_LONG`).
- Lower `MAX_FOLLOWS_PER_SESSION` and `MAX_LIKES_PER_SESSION` for less aggressive behavior.

### Bot does nothing during certain hours

This is the **sleep kill-switch** working as intended. The bot pauses between 10 PM and 7 AM to mimic human behavior. Adjust `SLEEP_START` and `SLEEP_END` in `config.py` if needed.

### "Permission denied" or antivirus blocks the bot

Some antivirus software may flag Playwright's browser. Add the bot folder to your antivirus exclusions, or temporarily disable real-time scanning while running the bot.

### Video upload fails

- Make sure the video file path is correct and the file exists
- TikTok has upload limits - try a smaller file (under 10 minutes, under 2GB)
- Ensure you're logged in (try option [2] to re-login first)

---

## Safety Notes

- The bot uses **no private APIs** - all actions go through the regular TikTok web interface
- Session limits are intentionally conservative to reduce risk of account flags
- The sleep kill-switch ensures zero activity during night hours
- Adaptive throttling automatically slows down when it detects CAPTCHA or rate-limit signals
- The bot uses human-like typing speeds, mouse movements, and scroll patterns
- All actions include randomized delays to avoid detectable patterns

---

## Stopping the Bot

- **Press `Ctrl+C`** in the command prompt window to gracefully stop the bot
- Or simply **close the command prompt window**
- The bot will clean up and save its state before exiting

---

## Disclaimer

This tool is provided for educational purposes. Use it responsibly and in compliance with TikTok's Terms of Service. The authors are not responsible for any account restrictions that may result from automated activity.
