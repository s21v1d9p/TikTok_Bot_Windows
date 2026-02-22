"""
bot_utils.py – Shared helper utilities for the TikTok Browser Bot.
Provides human-like delays, typing simulation, sleep-schedule checks,
and structured logging.
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime

from config import (
    CHALLENGE_CHECK_INTERVAL,
    DELAY_MEDIUM,
    LOG_FILE,
    SLEEP_END,
    SLEEP_START,
    TYPING_DELAY,
)

# ──────────────────────────────────────────────
# Logger Setup
# ──────────────────────────────────────────────
_log_format = "%(asctime)s | %(levelname)-8s | %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=_log_format,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("TikTokBot")


# ─────────────────────────────────────────────
# Action Counter (for periodic challenge checks)
# ─────────────────────────────────────────────
_action_counter: int = 0


def _maybe_check_challenge(page) -> None:
    """Run a CAPTCHA/rate-limit check every N actions."""
    global _action_counter
    _action_counter += 1
    if _action_counter % CHALLENGE_CHECK_INTERVAL == 0 and page is not None:
        from stealth import handle_challenge
        handle_challenge(page)


# ─────────────────────────────────────────────
# Random Delay Helpers
# ─────────────────────────────────────────────
def random_sleep(
    min_seconds: float | None = None,
    max_seconds: float | None = None,
    page=None,
) -> None:
    """Sleep for a random duration between *min_seconds* and *max_seconds*.

    When *page* is provided, uses idle_sleep from stealth module to
    perform micro-mouse-movements during the wait (human-like idle).
    Falls back to DELAY_MEDIUM from config when no range is supplied.
    """
    if min_seconds is None or max_seconds is None:
        min_seconds, max_seconds = DELAY_MEDIUM

    from stealth import get_throttle
    throttle = get_throttle()
    base_delay = random.uniform(min_seconds, max_seconds)
    delay = base_delay * throttle.delay_multiplier
    logger.debug("Sleeping %.2f s (base=%.2f, mult=%.2f)", delay, base_delay, throttle.delay_multiplier)

    if page is not None:
        from stealth import idle_sleep
        idle_sleep(page, delay)
    else:
        time.sleep(delay)


# ─────────────────────────────────────────────
# Human-Like Typing
# ─────────────────────────────────────────────
def human_type(page, selector: str, text: str) -> None:
    """Click *selector* and type *text* with context-aware delays
    (burst-type within words, pauses at boundaries).
    """
    logger.info("Typing %d chars into '%s'", len(text), selector)
    from stealth import human_click_element, human_type_advanced
    element = page.locator(selector).first
    human_type_advanced(page, element, text)


def human_type_element(page, element, text: str) -> None:
    """Same as ``human_type`` but operates on an already-resolved
    Playwright *ElementHandle / Locator*.
    """
    from stealth import human_type_advanced
    human_type_advanced(page, element, text)


# ──────────────────────────────────────────────
# Sleep-Schedule Kill Switch
# ──────────────────────────────────────────────
def check_sleep_schedule() -> bool:
    """Return ``True`` if the bot should be sleeping (kill-switch active).

    The window is defined by SLEEP_START and SLEEP_END in config.py.
    Handles the overnight wrap-around (e.g. 22:00 → 07:00).
    """
    current_hour = datetime.now().hour
    if SLEEP_START > SLEEP_END:
        # Overnight window (e.g. 22 → 7)
        return current_hour >= SLEEP_START or current_hour < SLEEP_END
    # Same-day window (e.g. 1 → 5 – unlikely but handled)
    return SLEEP_START <= current_hour < SLEEP_END


def wait_until_active() -> None:
    """Block execution until the sleep window has passed.

    Polls every 60 seconds and logs the waiting state.
    """
    while check_sleep_schedule():
        now = datetime.now().strftime("%H:%M:%S")
        logger.info(
            "[Kill-Switch] %s – Bot is sleeping (active window: %02d:00–%02d:00). "
            "Checking again in 60 s …",
            now,
            SLEEP_END,
            SLEEP_START,
        )
        time.sleep(60)
    logger.debug("[Kill-Switch] Active window – operations allowed.")


# ─────────────────────────────────────────────
# Misc Helpers
# ─────────────────────────────────────────────
def scroll_page(page, times: int = 3, direction: str = "down") -> None:
    """Scroll the page *times* times using smooth acceleration curves.

    Includes a guard for empty/non-growing pages to avoid repeated
    bouncing when TikTok serves a restricted shell.
    """
    from stealth import smooth_scroll
    stalled_rounds = 0
    for _ in range(times):
        before_h = 0
        try:
            before_h = page.evaluate("() => document.body ? document.body.scrollHeight : 0")
        except Exception:
            pass

        smooth_scroll(page, direction=direction, distance=random.randint(300, 700))
        random_sleep(1.0, 2.5, page=page)

        after_h = before_h
        try:
            after_h = page.evaluate("() => document.body ? document.body.scrollHeight : 0")
        except Exception:
            pass

        if direction == "down":
            if after_h <= before_h:
                stalled_rounds += 1
            else:
                stalled_rounds = 0

            if stalled_rounds >= 2 and after_h < 1400:
                logger.warning(
                    "Scroll stalled on low-height page (height=%s). "
                    "Stopping further scroll attempts.",
                    after_h,
                )
                break


def safe_click(page, selector: str, timeout: int = 5000) -> bool:
    """Try to click *selector* using human-like mouse movement;
    return ``True`` on success, ``False`` on timeout.
    """
    from stealth import human_click_element
    try:
        loc = page.locator(selector).first
        result = human_click_element(page, loc, timeout=timeout)
        _maybe_check_challenge(page)
        return result
    except Exception as exc:
        logger.warning("safe_click failed for '%s': %s", selector, exc)
        return False


def element_exists(page, selector: str, timeout: int = 3000) -> bool:
    """Return ``True`` if *selector* is visible on the page."""
    try:
        page.locator(selector).first.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False
