# Configuration Guide - TikTok Browser Bot

This guide explains all configuration options in `config.py`.

---

## Table of Contents

1. [Safety Limits](#safety-limits)
2. [Sleep Schedule](#sleep-schedule)
3. [Target Niche](#target-niche)
4. [Delay Settings](#delay-settings)
5. [Anti-Detection Settings](#anti-detection-settings)
6. [Debug Settings](#debug-settings)
7. [CSS Selectors](#css-selectors)

---

## Safety Limits

These settings control how many actions the bot performs per session (approximately every 2 hours).

```python
MAX_FOLLOWS_PER_SESSION = 8
MAX_LIKES_PER_SESSION = 20
MAX_VIDEOS_TO_WATCH = 7
FEED_SCROLL_ROUNDS = 7
```

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| `MAX_FOLLOWS_PER_SESSION` | 8 | 1-15 | Max accounts to follow per session |
| `MAX_LIKES_PER_SESSION` | 20 | 1-50 | Max videos to like per session |
| `MAX_VIDEOS_TO_WATCH` | 7 | 1-20 | Videos to watch in feed per session |
| `FEED_SCROLL_ROUNDS` | 7 | 1-15 | How many times to scroll the feed |

**Recommendations**:
- **Conservative**: `MAX_FOLLOWS = 3`, `MAX_LIKES = 10` (safer, slower growth)
- **Moderate**: `MAX_FOLLOWS = 8`, `MAX_LIKES = 20` (default, balanced)
- **Aggressive**: `MAX_FOLLOWS = 15`, `MAX_LIKES = 40` (higher risk of CAPTCHA)

---

## Sleep Schedule

The bot automatically pauses activity during specified hours.

```python
SLEEP_START = 22  # 10:00 PM
SLEEP_END = 7     # 7:00 AM
```

| Setting | Default | Description |
|---------|---------|-------------|
| `SLEEP_START` | 22 (10 PM) | Hour to stop all activity (24-hour format) |
| `SLEEP_END` | 7 (7 AM) | Hour to resume activity (24-hour format) |

**Examples**:
- `SLEEP_START = 22, SLEEP_END = 7` → Sleep from 10 PM to 7 AM
- `SLEEP_START = 23, SLEEP_END = 6` → Sleep from 11 PM to 6 AM
- `SLEEP_START = 0, SLEEP_END = 0` → No sleep (not recommended)

---

## Target Niche

Configure the niche/industry you want to target.

```python
TARGET_HASHTAG = "trading"

FALLBACK_HASHTAGS = [
    "forextrading", "daytrading", "cryptotrading",
    "stockmarket", "forex", "crypto",
]

NICHE_KEYWORDS = [
    "trading", "forex", "crypto", "stocks", "bitcoin",
    "ethereum", "daytrading", "investing", "stockmarket",
    "cryptocurrency", "trader", "forextrader",
    "options", "futures", "nifty",
    "market", "profit", "chart", "technical analysis",
    "swing", "scalping", "pips", "candlestick",
    "wallstreet", "nasdaq", "sp500", "dow jones",
    "bullish", "bearish", "breakout", "support resistance",
]
```

### Changing to a Different Niche

**Example: Fitness Niche**

```python
TARGET_HASHTAG = "fitness"

FALLBACK_HASHTAGS = [
    "workout", "gym", "bodybuilding",
    "fitnessmotivation", "fitfam", "health",
]

NICHE_KEYWORDS = [
    "fitness", "workout", "gym", "exercise", "health",
    "bodybuilding", "muscle", "training", "fitfam",
    "cardio", "strength", "weightloss", "nutrition",
    "personaltrainer", "crossfit", "yoga", "pilates",
]
```

**Example: Cooking Niche**

```python
TARGET_HASHTAG = "cooking"

FALLBACK_HASHTAGS = [
    "recipe", "foodie", "homecooking",
    "easyrecipes", "foodtiktok", "chef",
]

NICHE_KEYWORDS = [
    "cooking", "recipe", "food", "chef", "kitchen",
    "homemade", "delicious", "ingredients", "baking",
    "dinner", "lunch", "breakfast", "mealprep",
]
```

---

## Delay Settings

Control the timing between actions. All values are in seconds.

```python
DELAY_SHORT = (2.0, 4.5)
DELAY_MEDIUM = (5.0, 9.0)
DELAY_LONG = (10.0, 18.0)
TYPING_DELAY = (0.04, 0.18)
```

| Setting | Default | Description |
|---------|---------|-------------|
| `DELAY_SHORT` | 2-4.5 sec | Quick pauses between rapid actions |
| `DELAY_MEDIUM` | 5-9 sec | Standard pauses between actions |
| `DELAY_LONG` | 10-18 sec | Longer pauses for major transitions |
| `TYPING_DELAY` | 0.04-0.18 sec | Delay between keystrokes |

**Recommendations**:
- **Faster** (higher risk): Reduce all values by 50%
- **Safer** (lower risk): Increase all values by 50%

---

## Anti-Detection Settings

```python
DESKTOP_ONLY_UA = True

MOUSE_STEPS_MIN = 12
MOUSE_STEPS_MAX = 80
MOUSE_STEP_DELAY = (0.003, 0.018)

IDLE_MOUSE_DRIFT_CHANCE = 0.15
IDLE_MICRO_SCROLL_CHANCE = 0.05

CHALLENGE_CHECK_INTERVAL = 5
```

| Setting | Default | Description |
|---------|---------|-------------|
| `DESKTOP_ONLY_UA` | True | Use desktop user agents only |
| `MOUSE_STEPS_MIN` | 12 | Minimum steps for mouse movement |
| `MOUSE_STEPS_MAX` | 80 | Maximum steps for mouse movement |
| `MOUSE_STEP_DELAY` | 0.003-0.018 sec | Delay between mouse steps |
| `IDLE_MOUSE_DRIFT_CHANCE` | 0.15 (15%) | Chance of random mouse movement during idle |
| `IDLE_MICRO_SCROLL_CHANCE` | 0.05 (5%) | Chance of small scroll during idle |
| `CHALLENGE_CHECK_INTERVAL` | 5 | Check for CAPTCHA every N actions |

**Note**: These settings are optimized for stealth. Changing them may increase detection risk.

---

## Debug Settings

```python
DEBUG_CAPTCHA_CAPTURE = True
DEBUG_DIR = os.path.join(BASE_DIR, "debug")
```

| Setting | Default | Description |
|---------|---------|-------------|
| `DEBUG_CAPTCHA_CAPTURE` | True | Save screenshots when CAPTCHA detected |
| `DEBUG_DIR` | `debug/` | Folder for debug screenshots |

When `DEBUG_CAPTCHA_CAPTURE` is True:
- Screenshots are saved to `debug/captcha_TIMESTAMP.png`
- HTML is saved to `debug/captcha_TIMESTAMP.html`
- Useful for diagnosing CAPTCHA issues

---

## CSS Selectors

These selectors tell the bot how to find elements on TikTok's pages. **Do not modify unless TikTok changes their UI.**

```python
SELECTORS = {
    "login_qr_container": '[data-e2e="qrcode-image"]',
    "logged_in_indicators": [...],
    "logged_out_indicators": [...],
    "video_card": '[data-e2e="recommend-list-item-container"]',
    "follow_button": '[data-e2e="follow-button"]',
    # ... more selectors
}
```

If the bot stops working after a TikTok update:
1. Check `bot.log` for element not found errors
2. Inspect TikTok's page structure (F12 in browser)
3. Update the relevant selectors

---

## Feature Toggles

Enable or disable specific bot features:

```python
ENABLE_MUTUALS = True
ENABLE_SUGGESTED = True
```

| Setting | Default | Description |
|---------|---------|-------------|
| `ENABLE_MUTUALS` | True | Enable mutual connection growth feature |
| `ENABLE_SUGGESTED` | True | Enable suggested accounts feature |

Set to `False` to disable a feature if you only want specific functionality.

---

## Suggested Accounts Settings

```python
MAX_SUGGESTED_FOLLOWS = 3
```

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_SUGGESTED_FOLLOWS` | 3 | Max follows from suggested sidebar per session |

---

## Hashtag Transition Settings

```python
HASHTAG_TRANSITION_PAUSE_MIN = 35.0
HASHTAG_TRANSITION_PAUSE_MAX = 75.0
```

| Setting | Default | Description |
|---------|---------|-------------|
| `HASHTAG_TRANSITION_PAUSE_MIN` | 35 sec | Minimum pause before opening hashtag |
| `HASHTAG_TRANSITION_PAUSE_MAX` | 75 sec | Maximum pause before opening hashtag |

These pauses mimic natural browsing behavior before navigating to hashtag pages.

---

## Throttle Settings

The adaptive throttle automatically slows down when detecting suspicious signals.

```python
THROTTLE_WARN_THRESHOLD = 3.0
THROTTLE_CRITICAL_THRESHOLD = 6.0
THROTTLE_CRITICAL_PAUSE = (120, 300)
THROTTLE_WARN_PAUSE = (30, 60)
```

| Setting | Default | Description |
|---------|---------|-------------|
| `THROTTLE_WARN_THRESHOLD` | 3.0 | Suspicion score to trigger warning |
| `THROTTLE_CRITICAL_THRESHOLD` | 6.0 | Suspicion score to trigger critical pause |
| `THROTTLE_CRITICAL_PAUSE` | 120-300 sec | Pause duration when critical |
| `THROTTLE_WARN_PAUSE` | 30-60 sec | Pause duration on warning |

**How it works**:
- Each CAPTCHA adds +2.5 to suspicion score
- Each soft-block adds +1.0
- Score decays by -0.2 after clean actions
- Higher scores = longer delays

---

## Quick Reference

### Recommended Settings for New Accounts

```python
MAX_FOLLOWS_PER_SESSION = 2
MAX_LIKES_PER_SESSION = 5
MAX_VIDEOS_TO_WATCH = 5
DELAY_MEDIUM = (8.0, 15.0)  # Longer delays
```

### Recommended Settings for Established Accounts

```python
MAX_FOLLOWS_PER_SESSION = 8
MAX_LIKES_PER_SESSION = 20
MAX_VIDEOS_TO_WATCH = 7
DELAY_MEDIUM = (5.0, 9.0)  # Default delays
```

### Maximum Safety Settings

```python
MAX_FOLLOWS_PER_SESSION = 1
MAX_LIKES_PER_SESSION = 3
MAX_VIDEOS_TO_WATCH = 3
DELAY_MEDIUM = (15.0, 25.0)
SLEEP_START = 20  # 8 PM
SLEEP_END = 8     # 8 AM
```
