"""
config.py – Central configuration for the TikTok Browser Bot.
All tuneable constants, file paths, and UI selectors live here.
"""

import os

# ──────────────────────────────────────────────
# Directories & Paths
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_PATH = os.path.join(BASE_DIR, "auth.json")
BROWSER_DATA_DIR = os.path.join(BASE_DIR, "chrome_profile")
LOG_FILE = os.path.join(BASE_DIR, "bot.log")
SCHEDULE_FILE = os.path.join(BASE_DIR, "video_schedule.json")

# ──────────────────────────────────────────────
# Sleep / Kill-Switch Schedule (24-hour format)
# Bot will NOT perform any actions between these hours.
# Client requirement: 10 PM – 7 AM
# ──────────────────────────────────────────────
SLEEP_START = 22  # 10:00 PM local time
SLEEP_END = 7     # 07:00 AM local time

# ──────────────────────────────────────────────
# Safety Limits (per session / per cycle)
# ──────────────────────────────────────────────
MAX_FOLLOWS_PER_SESSION = 8
MAX_LIKES_PER_SESSION = 20
MAX_VIDEOS_TO_WATCH = 7
FEED_SCROLL_ROUNDS = 7

# Isolation (for CAPTCHA debugging: disable one flow at a time)
ENABLE_MUTUALS = True
ENABLE_SUGGESTED = True

# Hashtag transition: pause on home before opening #trading (seconds)
HASHTAG_TRANSITION_PAUSE_MIN = 35.0
HASHTAG_TRANSITION_PAUSE_MAX = 75.0

# Suggested sidebar: max follows from suggested cards per session
MAX_SUGGESTED_FOLLOWS = 3

# Debug: save screenshot + HTML when CAPTCHA detected (phase logged)
DEBUG_CAPTCHA_CAPTURE = True
DEBUG_DIR = os.path.join(BASE_DIR, "debug")

# ──────────────────────────────────────────────
# Target Niche
# ──────────────────────────────────────────────
TARGET_HASHTAG = "trading"

# Fallback hashtags when primary yields no results
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

# ──────────────────────────────────────────────
# Random Delay Ranges (seconds)
# ──────────────────────────────────────────────
DELAY_SHORT = (2.0, 4.5)
DELAY_MEDIUM = (5.0, 9.0)
DELAY_LONG = (10.0, 18.0)
TYPING_DELAY = (0.04, 0.18)  # per-keystroke

# ──────────────────────────────────────────────
# Anti-Detection / Stealth Settings
# ──────────────────────────────────────────────
# Force desktop-only user agents (mobile UAs break all selectors)
DESKTOP_ONLY_UA = True

# Mouse movement: Bézier-curve steps and speed
MOUSE_STEPS_MIN = 12
MOUSE_STEPS_MAX = 80
MOUSE_STEP_DELAY = (0.003, 0.018)  # seconds between path points

# Idle simulation: probability of micro-actions during waits
IDLE_MOUSE_DRIFT_CHANCE = 0.15  # chance of random mouse drift per idle tick
IDLE_MICRO_SCROLL_CHANCE = 0.05  # chance of tiny scroll per idle tick

# Adaptive throttle
THROTTLE_WARN_THRESHOLD = 3.0
THROTTLE_CRITICAL_THRESHOLD = 6.0
THROTTLE_CRITICAL_PAUSE = (120, 300)  # seconds to pause when critical
THROTTLE_WARN_PAUSE = (30, 60)        # seconds to pause on challenge

# Challenge check frequency: run after every N actions
CHALLENGE_CHECK_INTERVAL = 5

# Browser launch policy
# Keep this True to avoid falling back to regular Chrome/CDP.
PHANTOMWRIGHT_ONLY = True

# Retry launch because patched Chromium may fail on first attempt
# when stale lock files or transient OS-level issues exist.
PHANTOMWRIGHT_LAUNCH_RETRIES = 3

# ──────────────────────────────────────────────
# TikTok URLs
# ──────────────────────────────────────────────
TIKTOK_BASE = "https://www.tiktok.com"
TIKTOK_LOGIN = f"{TIKTOK_BASE}/login"
TIKTOK_UPLOAD = f"{TIKTOK_BASE}/upload"
TIKTOK_SEARCH = f"{TIKTOK_BASE}/search"
TIKTOK_TAG_URL = f"{TIKTOK_BASE}/tag/{TARGET_HASHTAG}"

# ──────────────────────────────────────────────
# CSS / XPath Selectors
# TikTok frequently changes its DOM – update these
# whenever selectors break.
#
# Strategy: use data-e2e attributes first, then
# stable class patterns, then generic fallbacks.
# ──────────────────────────────────────────────
SELECTORS = {
    # ── Login / Logged-in Detection ──
    "login_qr_container": '[data-e2e="qrcode-image"]',

    # POSITIVE logged-in indicators (check ANY of these)
    "logged_in_indicators": [
        '[data-e2e="nav-profile"]',            # Profile icon in sidebar
        '[data-e2e="profile-icon"]',           # Top-right profile icon
        '[data-e2e="upload-icon"]',            # Upload icon
        '[href="/upload"]',                    # Upload link
        '[data-e2e="messages-icon"]',          # Messages icon (definitely logged in)
    ],

    # NEGATIVE logged-out indicators
    "logged_out_indicators": [
        '[data-e2e="login-button"]',           # Explicit login button
        'button:has-text("Log in")',           # Text-based login button
    ],

    # ── Feed / For You Page ──
    "video_card": '[data-e2e="recommend-list-item-container"]',
    "video_desc": '[data-e2e="browse-video-desc"]',
    "video_author": '[data-e2e="video-author-uniqueid"]',

    # Like button selectors (multiple fallbacks)
    "like_button": '[data-e2e="like-icon"]',
    "like_button_alt": '[data-e2e="browse-like-icon"]',

    # Detecting if already liked: check aria-pressed or color class
    "like_button_active_checks": [
        '[data-e2e="like-icon"][class*="active"]',
        '[data-e2e="like-icon"][aria-pressed="true"]',
        '[data-e2e="like-icon"] svg[fill="rgb(254, 44, 85)"]',
        '[data-e2e="like-icon"] svg[fill="#FE2C55"]',
    ],

    # ── Search ──
    "search_input": 'input[data-e2e="search-user-input"]',
    "search_button": 'button[data-e2e="search-button"]',
    "search_user_link": '[data-e2e="search-user-info-container"]',

    # ── Profile / Follow ──
    "follow_button": '[data-e2e="follow-button"]',
    "follow_button_alt": 'button:has-text("Follow")',
    "followers_link": '[data-e2e="followers-count"]',
    "following_count": '[data-e2e="following-count"]',
    "bio_text": '[data-e2e="user-bio"]',
    "user_title": '[data-e2e="user-title"]',
    "user_subtitle": '[data-e2e="user-subtitle"]',

    # Suggested accounts (multiple selector attempts)
    "suggested_accounts_selectors": [
        '[data-e2e="suggest-accounts"]',
        '[class*="SuggestedAccounts"]',
        '[class*="suggested"]',
        'aside [class*="recommend"]',
    ],
    "user_card": '[data-e2e="user-card"]',
    "user_card_desc": '[data-e2e="user-card-desc"]',

    # Mutual / "Followed by" indicators
    # These are text strings that appear on profile pages when
    # the logged-in user shares mutual connections with the profile
    "mutual_indicator_texts": [
        "followed by",
        "mutual connections",
        "friends with",
        "followed by your friend",
        "followers you follow",
        "mutual friend",
        "you may know",
        "also follows",
    ],

    # CSS selectors for mutual indicator elements on profile pages
    "mutual_indicator_selectors": [
        '[data-e2e="mutual-links"]',
        '[class*="mutual"]',
        '[class*="MutualFollower"]',
        '[class*="mutualFollower"]',
        'a[class*="followedBy"]',
    ],

    # ── Upload ──
    "upload_iframe": "iframe",
    "upload_file_input": 'input[type="file"]',
    "caption_editor": '[data-e2e="caption-editor"]',
    "caption_input": '[contenteditable="true"]',
    "post_button": '[data-e2e="post-button"]',
    "post_button_alt": 'button:has-text("Post")',
    "upload_confirm_toast": '[class*="toast"]',
    "upload_success_indicators": [
        '[class*="toast"]',
        '[class*="success"]',
        'text="Your video has been uploaded"',
    ],
}
