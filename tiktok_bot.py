"""
tiktok_bot.py – Main TikTok Browser Bot class.

Handles browser lifecycle, authentication (manual QR-code login + cookie
persistence), feed interaction, "Mutuals" network growth, and video upload.
"""

from __future__ import annotations

import json
import os
import platform
import random
import re
import time
import warnings

# Phantomwright's add_init_script raises UserWarning; we use it intentionally.
warnings.filterwarnings("ignore", message=".*add_init_script.*", category=UserWarning)

from phantomwright.sync_api import sync_playwright
from phantomwright.stealth import Stealth

from bot_utils import (
    element_exists,
    human_type,
    human_type_element,
    logger,
    random_sleep,
    safe_click,
    scroll_page,
    wait_until_active,
)
from config import (
    BASE_DIR,
    BROWSER_DATA_DIR,
    COOKIES_PATH,
    DELAY_LONG,
    DELAY_MEDIUM,
    DELAY_SHORT,
    ENABLE_MUTUALS,
    ENABLE_SUGGESTED,
    FALLBACK_HASHTAGS,
    FEED_SCROLL_ROUNDS,
    HASHTAG_TRANSITION_PAUSE_MAX,
    HASHTAG_TRANSITION_PAUSE_MIN,
    MAX_FOLLOWS_PER_SESSION,
    MAX_LIKES_PER_SESSION,
    MAX_SUGGESTED_FOLLOWS,
    MAX_VIDEOS_TO_WATCH,
    NICHE_KEYWORDS,
    PHANTOMWRIGHT_LAUNCH_RETRIES,
    SCHEDULE_FILE,
    SELECTORS,
    TARGET_HASHTAG,
    TIKTOK_BASE,
    TIKTOK_LOGIN,
    TIKTOK_TAG_URL,
    TIKTOK_UPLOAD,
)
from stealth import (
    get_fingerprint_scripts,
    get_throttle,
    handle_challenge,
    human_click_element,
    human_hashtag_warmup,
    human_mouse_warmup,
    human_profile_warmup,
    human_scroll_next_video,
    idle_sleep,
    random_viewport,
)


def _get_desktop_ua() -> str | None:
    """Return None to let the browser's real UA pass through.

    Using fake_useragent creates a mismatch between the HTTP User-Agent
    header and the browser's actual capabilities/version, which is a
    major bot detection signal.  Phantomwright's patched Chromium has its
    own legitimate UA that matches its actual engine — we should use it.
    """
    # Return None so the browser context doesn't override the real UA.
    # The browser's built-in UA will match its actual engine version,
    # avoiding the mismatch that triggers detection.
    return None


class TikTokBot:
    """Encapsulates all browser-level TikTok automation."""

    # ──────────────────────────────────────────
    # Initialisation & Teardown
    # ──────────────────────────────────────────
    def __init__(self) -> None:
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._closed = False
        self._chrome_process = None
        self._stealth = None
        self._user_agent = _get_desktop_ua()
        self._session_behavior = self._build_session_behavior()

        self._follows_this_session = 0
        self._likes_this_session = 0
        self._captcha_hit_this_session = False
        self._content_blocked_this_session = False

    @staticmethod
    def _build_session_behavior() -> dict:
        """Generate per-session behavior variance to avoid fixed rhythms."""
        watch_min = random.uniform(8.0, 15.0)
        watch_max = random.uniform(20.0, 45.0)
        return {
            "watch_min": min(watch_min, watch_max - 2.0),
            "watch_max": watch_max,
            "profile_eval_pause": (random.uniform(25.0, 40.0), random.uniform(45.0, 75.0)),
            # Occasionally take a long break mid-feed (human checking phone, reading)
            "long_pause_chance": random.uniform(0.10, 0.25),
            "long_pause_range": (random.uniform(15.0, 25.0), random.uniform(30.0, 60.0)),
        }

    def _apply_stealth_layers(self) -> None:
        """Apply playwright-stealth and custom fingerprint scripts."""
        if not self.context or not self.page:
            return

        if self._stealth is None:
            self._stealth = Stealth(
                # Let overrides use defaults (don't pass None — it breaks JS evasion scripts).
                navigator_languages_override=("en-US", "en"),
                # Keep media_codecs off (breaks video playback when spoofed).
                # But enable all other safe evasions to reduce detection surface.
                media_codecs=False,
                navigator_user_agent=True,    # let stealth fix UA inconsistencies
                navigator_platform=True,      # let stealth fix platform leaks
                sec_ch_ua=True,               # fix Client Hints header
            )

        try:
            self._stealth.apply_stealth_sync(self.context)
        except Exception as exc:
            logger.debug("Stealth apply on context failed: %s", exc)

        try:
            self._stealth.apply_stealth_sync(self.page)
        except Exception as exc:
            logger.debug("Stealth apply on page failed: %s", exc)

        # Critical fingerprint hardening (webdriver, plugins, canvas, WebGL)
        try:
            self.context.add_init_script(get_fingerprint_scripts(self._user_agent))
        except Exception as exc:
            logger.debug("Init fingerprint script failed: %s", exc)

        try:
            self.context.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
            })
        except Exception as exc:
            logger.debug("Setting extra headers failed: %s", exc)

    def _detect_shell_or_blocked_page(self, page_kind: str) -> tuple[bool, dict]:
        """Return (blocked, diagnostics) if TikTok served an empty shell/restricted page."""
        diagnostics = {
            "video_cards": 0,
            "profile_anchors": 0,
            "skeletons": 0,
            "scroll_height": 0,
            "has_sigi_state": False,
            "blocked_text": "",
        }
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Post-load delay: TikTok's SPA needs extra time to hydrate content
        time.sleep(random.uniform(3.0, 5.0))

        try:
            diagnostics = self.page.evaluate("""() => {
                const text = (document.body?.innerText || "").toLowerCase();
                const blockedHints = [
                    "something went wrong",
                    "too many requests",
                    "try again later",
                    "temporarily unavailable",
                    "verify you are human",
                    "security verification",
                    "access denied",
                    "having trouble playing"
                ];
                const matchedHint = blockedHints.find((h) => text.includes(h)) || "";
                return {
                    video_cards: document.querySelectorAll(
                        '[data-e2e="recommend-list-item-container"],[data-e2e="search-card-item"],a[href*="/video/"]'
                    ).length,
                    profile_anchors: document.querySelectorAll('a[href*="/@"]').length,
                    skeletons: document.querySelectorAll(
                        '[class*="skeleton"],[data-e2e*="skeleton"],[class*="Skeleton"]'
                    ).length,
                    scroll_height: document.body ? document.body.scrollHeight : 0,
                    has_sigi_state: Boolean(document.querySelector('#SIGI_STATE')),
                    blocked_text: matchedHint
                };
            }""")
        except Exception:
            pass

        blocked = False
        low_content = (
            diagnostics["video_cards"] == 0
            and diagnostics["profile_anchors"] <= 1
            and diagnostics["scroll_height"] < 1200
        )
        blocked_hint = (diagnostics.get("blocked_text") or "").strip()
        # On feed, "having trouble playing" is often a single-video failure, not a full-page block.
        # Don't trigger refresh; we'll scroll to next video instead.
        if blocked_hint and not (page_kind == "feed" and blocked_hint == "having trouble playing"):
            blocked = True
        elif page_kind == "hashtag":
            blocked = diagnostics["video_cards"] == 0 and diagnostics["profile_anchors"] <= 2
        elif page_kind == "profile":
            profile_title_ok = element_exists(self.page, SELECTORS["user_title"], timeout=1200)
            bio_ok = element_exists(self.page, SELECTORS["bio_text"], timeout=1200)
            blocked = not profile_title_ok and not bio_ok and low_content
        elif page_kind == "feed":
            blocked = diagnostics["video_cards"] == 0 and diagnostics["profile_anchors"] == 0 and low_content

        return blocked, diagnostics

    def _ensure_page_has_content(
        self,
        page_kind: str,
        max_retries: int = 2,
        retry_scroll: bool = True,
    ) -> bool:
        """Retry light interactions and confirm content exists before continuing."""
        for attempt in range(max_retries + 1):
            blocked, diag = self._detect_shell_or_blocked_page(page_kind)
            if not blocked:
                if attempt > 0:
                    logger.info("Recovered %s page content on retry %d.", page_kind, attempt)
                return True

            matched_hint = diag.get("blocked_text", "")
            logger.warning(
                "Likely restricted/empty %s page (attempt %d/%d): cards=%s profiles=%s height=%s skeletons=%s matchedHint='%s'",
                page_kind,
                attempt + 1,
                max_retries + 1,
                diag.get("video_cards"),
                diag.get("profile_anchors"),
                diag.get("scroll_height"),
                diag.get("skeletons"),
                matched_hint,
            )
            if attempt < max_retries:
                # Refresh the page — often resolves TikTok's transient errors
                try:
                    logger.info("Refreshing page to recover from '%s' …", matched_hint or 'empty page')
                    self.page.reload(wait_until="domcontentloaded")
                except Exception:
                    pass
                if retry_scroll:
                    try:
                        human_scroll_next_video(self.page)
                    except Exception:
                        pass
                random_sleep(4.0, 8.0, page=self.page)

        return False

    def _mark_soft_block(self, reason: str) -> None:
        """Mark current session as content-restricted and back off.

        IMPORTANT: This does NOT set _captcha_hit_this_session.
        A single content-blocked page should not kill the entire session.
        Only a real CAPTCHA should prevent all remaining tasks.
        """
        self._content_blocked_this_session = True
        try:
            get_throttle().bump(1.0, reason=f"soft-block:{reason}")
        except Exception:
            pass
        cooldown = random.uniform(15, 35)
        logger.warning("Soft-block suspected (%s). Backing off for %.0f s.", reason, cooldown)
        idle_sleep(self.page, cooldown)

    def _clear_profile_locks(self) -> None:
        """Remove stale Chrome profile lock files that can cause launch failures."""
        for lock_file in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            lock_path = os.path.join(BROWSER_DATA_DIR, lock_file)
            try:
                os.remove(lock_path)
            except FileNotFoundError:
                pass

    def _launch_browser(self, headless: bool = False) -> None:
        """Launch browser using phantomwright's patched Chromium binary.

        Strategy:
        1. PRIMARY: launch_persistent_context with phantomwright's patched
           Chromium (with retries and lock cleanup — fixes "Mach rendezvous"
           failures on macOS).
        2. FALLBACK A: If persistent context always fails, try launch() with
           ephemeral profile (no user_data_dir); session restored via auth.json.
        3. FALLBACK B: Real Chrome + CDP if patched Chromium cannot start.
        """
        os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
        viewport = random_viewport()

        self._clear_profile_locks()

        # Kill any leftover Chrome/Chromium on debug port
        try:
            import subprocess as _sp
            result = _sp.run(
                ["lsof", "-ti", ":9222"],
                capture_output=True, text=True,
            )
            if result.stdout.strip():
                for pid in result.stdout.strip().split("\n"):
                    _sp.run(["kill", "-9", pid.strip()], capture_output=True)
                time.sleep(1)
        except Exception:
            pass

        chromium_args = [
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=TranslateUI",
            "--disable-sync",
            "--hide-crash-restore-bubble",
            "--disable-session-crashed-bubble",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-blink-features=AutomationControlled",
        ]

        # On macOS, persistent context often fails (Mach rendezvous / SSL). Try ephemeral first.
        _is_mac = platform.system() == "Darwin"
        last_persistent_err = None
        ephemeral_err = None

        if _is_mac:
            # ── macOS: try ephemeral first (one clean attempt, no noisy failures) ──
            try:
                logger.info(
                    "Launching phantomwright patched Chromium (ephemeral profile; session from auth.json) …"
                )
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(
                    headless=headless,
                    args=chromium_args,
                    ignore_default_args=["--enable-automation"],
                )
                self.context = self.browser.new_context(
                    viewport=viewport,
                    locale="en-US",
                    timezone_id="America/New_York",
                )
                self.page = self.context.new_page()
                self._apply_stealth_layers()
                self.page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)
                if "tiktok.com" in (self.page.url or "").lower():
                    logger.info(
                        "Phantomwright patched Chromium ready (viewport=%dx%d).",
                        viewport["width"], viewport["height"],
                    )
                    return
                raise RuntimeError(f"TikTok not reachable (got {self.page.url})")
            except Exception as e:
                ephemeral_err = e
                logger.warning("Patched Chromium (ephemeral) failed: %s. Trying persistent context …", e)
                try:
                    if self.context:
                        self.context.close()
                except Exception:
                    pass
                try:
                    if self.browser:
                        self.browser.close()
                except Exception:
                    pass
                try:
                    if self.playwright:
                        self.playwright.stop()
                except Exception:
                    pass
                self.context = None
                self.page = None
                self.browser = None
                self.playwright = None

        # ── Persistent context (with retries; skipped on macOS if ephemeral already succeeded) ──
        for attempt in range(1, PHANTOMWRIGHT_LAUNCH_RETRIES + 1):
            try:
                if attempt > 1:
                    self._clear_profile_locks()
                    time.sleep(2)
                logger.info(
                    "Launching phantomwright patched Chromium (persistent, attempt %d/%d) …",
                    attempt, PHANTOMWRIGHT_LAUNCH_RETRIES,
                )
                self.playwright = sync_playwright().start()
                self.context = self.playwright.chromium.launch_persistent_context(
                    user_data_dir=os.path.abspath(BROWSER_DATA_DIR),
                    headless=headless,
                    viewport=viewport,
                    locale="en-US",
                    timezone_id="America/New_York",
                    args=chromium_args,
                    ignore_default_args=["--enable-automation"],
                )
                self.browser = self.context.browser
                self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
                self._apply_stealth_layers()
                self.page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)
                if "tiktok.com" in (self.page.url or "").lower():
                    logger.info(
                        "Phantomwright patched Chromium ready (viewport=%dx%d).",
                        viewport["width"], viewport["height"],
                    )
                    return
                raise RuntimeError(f"TikTok not reachable (got {self.page.url})")
            except Exception as nav_err:
                try:
                    if self.context:
                        self.context.close()
                except Exception:
                    pass
                self.context = None
                self.page = None
                self.browser = None
                if self.playwright:
                    try:
                        self.playwright.stop()
                    except Exception:
                        pass
                    self.playwright = None
                last_persistent_err = nav_err
                logger.warning("Patched Chromium (persistent) attempt %d failed: %s", attempt, nav_err)
                continue

        if ephemeral_err is None:
            logger.info("Persistent context failed. Trying ephemeral profile …")
            try:
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(
                    headless=headless,
                    args=chromium_args,
                    ignore_default_args=["--enable-automation"],
                )
                self.context = self.browser.new_context(
                    viewport=viewport,
                    locale="en-US",
                    timezone_id="America/New_York",
                )
                self.page = self.context.new_page()
                self._apply_stealth_layers()
                self.page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)
                if "tiktok.com" in (self.page.url or "").lower():
                    logger.info(
                        "Phantomwright patched Chromium ready (ephemeral, viewport=%dx%d).",
                        viewport["width"], viewport["height"],
                    )
                    return
                raise RuntimeError(f"TikTok not reachable (got {self.page.url})")
            except Exception as e:
                ephemeral_err = e
                try:
                    if self.context:
                        self.context.close()
                except Exception:
                    pass
                try:
                    if self.browser:
                        self.browser.close()
                except Exception:
                    pass
                try:
                    if self.playwright:
                        self.playwright.stop()
                except Exception:
                    pass
                self.context = None
                self.page = None
                self.browser = None
                self.playwright = None

        logger.info(
            "Patched Chromium failed (%s). Using CDP fallback.",
            last_persistent_err or ephemeral_err,
        )

        # ── FALLBACK: User's real Chrome + CDP ──
        chrome_path = self._find_chrome()
        if not chrome_path:
            raise RuntimeError(
                "Google Chrome not found. Please install Chrome.\n"
                "On Mac: /Applications/Google Chrome.app\n"
                "On Windows: C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\n"
                "On Linux: google-chrome or chromium-browser"
            )

        cdp_port = 9222
        import subprocess
        chrome_args = [
            chrome_path,
            f"--remote-debugging-port={cdp_port}",
            f"--user-data-dir={os.path.abspath(BROWSER_DATA_DIR)}",
            f"--window-size={viewport['width']},{viewport['height']}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=TranslateUI",
            "--disable-sync",
            "--hide-crash-restore-bubble",
            "--disable-session-crashed-bubble",
            "--autoplay-policy=no-user-gesture-required",
            "https://www.tiktok.com",
        ]

        logger.info("Launching real Chrome (CDP fallback): %s", chrome_path)
        self._chrome_process = subprocess.Popen(
            chrome_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        import urllib.request
        ws_url = None
        for attempt in range(20):
            time.sleep(1)
            try:
                resp = urllib.request.urlopen(
                    f"http://127.0.0.1:{cdp_port}/json/version", timeout=2
                )
                data = json.loads(resp.read().decode())
                ws_url = data.get("webSocketDebuggerUrl", "")
                if ws_url:
                    logger.info("Chrome DevTools ready: %s", ws_url[:60])
                    break
            except Exception:
                pass

        if not ws_url:
            raise RuntimeError(
                "Chrome started but DevTools not reachable on port "
                f"{cdp_port}. Is another Chrome instance running?"
            )

        if not self.playwright:
            self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.connect_over_cdp(ws_url)
        self.context = self.browser.contexts[0]
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()

        self._apply_stealth_layers()

        logger.info(
            "Connected via CDP fallback (port %d, viewport=%dx%d). "
            "⚠️  Profile visits may trigger CAPTCHAs — patched Chromium preferred.",
            cdp_port, viewport["width"], viewport["height"],
        )

    @staticmethod
    def _find_chrome() -> str | None:
        """Find the real Chrome executable on the system."""
        system = platform.system()

        if system == "Darwin":
            paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            ]
        elif system == "Windows":
            paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ]
        else:  # Linux
            paths = [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
                "/snap/bin/chromium",
            ]

        for path in paths:
            if os.path.isfile(path):
                return path

        import shutil
        for name in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
            found = shutil.which(name)
            if found:
                return found

        return None

    def close(self) -> None:
        """Gracefully shut down browser and Playwright (idempotent)."""
        if self._closed:
            return
        self._closed = True

        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass

        # Kill Chrome subprocess if we launched one (CDP fallback)
        try:
            if hasattr(self, "_chrome_process") and self._chrome_process:
                self._chrome_process.terminate()
                self._chrome_process.wait(timeout=5)
        except Exception:
            try:
                self._chrome_process.kill()
            except Exception:
                pass

        logger.info("Browser closed.")

    # ──────────────────────────────────────────
    # Authentication
    # ──────────────────────────────────────────
    def login_manual(self) -> None:
        """First-run login flow.

        Opens TikTok login page so the user can scan the QR code or
        log in manually.  Once authenticated, cookies are saved to
        COOKIES_PATH for all future runs.
        """
        logger.info("=== MANUAL LOGIN MODE ===")
        self._launch_browser(headless=False)

        self.page.goto(TIKTOK_LOGIN, wait_until="domcontentloaded")
        random_sleep(*DELAY_MEDIUM)

        logger.info(
            "Please log in manually (QR code / credentials). "
            "The bot will wait up to 180 seconds …"
        )

        # Poll for logged-in state using POSITIVE detection
        logged_in = False
        for attempt in range(180):
            if self._check_logged_in():
                logged_in = True
                break
            time.sleep(1)
            if attempt % 15 == 0 and attempt > 0:
                logger.info("Still waiting for login … (%d s elapsed)", attempt)

        if not logged_in:
            logger.warning(
                "Login not detected after 180 s. Saving cookies anyway – "
                "you may need to re-run if they are invalid."
            )

        self._save_cookies()
        logger.info("Session cookies saved to %s", COOKIES_PATH)
        random_sleep(*DELAY_SHORT)
        # NOTE: close() is called here; main.py should NOT double-close

    def login_auto(self) -> bool:
        """Load saved session and verify it is still valid.

        With the real Chrome + CDP approach, cookies persist natively in the
        Chrome profile directory.  We check if the session is already valid
        first, and only inject cookies from auth.json as a fallback.

        Returns ``True`` if login succeeds, ``False`` otherwise.
        """
        logger.info("=== AUTO LOGIN MODE ===")

        self._launch_browser(headless=False)

        # The page may already be at tiktok.com from the Chrome launch
        try:
            current_url = self.page.url
            if "tiktok.com" not in current_url:
                self.page.goto(TIKTOK_BASE, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            logger.warning("Initial page load slow: %s", e)

        random_sleep(*DELAY_MEDIUM)

        logger.info("Current URL after navigation: %s", self.page.url)

        # ── Check 1: Chrome profile may already have a valid session ──
        if self._check_logged_in():
            logger.info("Auto-login successful – Chrome profile session is valid.")
            return True

        # ── Check 2: Try loading cookies from auth.json ──
        if os.path.isfile(COOKIES_PATH):
            logger.info("No active session in Chrome profile, loading cookies from auth.json …")
            self._load_cookies()
            try:
                self.page.reload(wait_until="domcontentloaded", timeout=60000)
            except Exception:
                pass
            random_sleep(*DELAY_MEDIUM)

            if self._check_logged_in():
                logger.info("Auto-login successful via auth.json cookies.")
                return True

            # Extra wait + retry
            logger.info("First login check negative, waiting 5s and retrying …")
            random_sleep(4.0, 6.0)

            if self._check_logged_in():
                logger.info("Auto-login successful on retry – session is valid.")
                return True

        # Definitely not logged in
        debug_screenshot = os.path.join(BASE_DIR, "debug_screenshot.png")
        self.page.screenshot(path=debug_screenshot)
        logger.info("Debug screenshot saved to: %s", debug_screenshot)
        logger.error(
            "Auto-login failed – cookies may have expired. "
            "Please re-run with option [2] for manual login."
        )
        self.close()
        return False

    def _check_logged_in(self) -> bool:
        """Return True if positive logged-in indicators are found.

        Checks for:
        1. Negative indicators (Login button) -> returns False immediately.
        2. Positive indicators (Profile/Upload icon) -> returns True.
        """
        # 1. Check for explicit "Log in" buttons
        for sel in SELECTORS["logged_out_indicators"]:
            try:
                if element_exists(self.page, sel, timeout=800):
                    logger.debug("Logged-out indicator found: %s", sel)
                    return False
            except Exception:
                pass

        # 2. Check for positive logged-in elements
        for selector in SELECTORS["logged_in_indicators"]:
            try:
                if element_exists(self.page, selector, timeout=1500):
                    logger.debug("Logged-in indicator found: %s", selector)
                    return True
            except Exception:
                continue

        return False

    def _save_cookies(self) -> None:
        cookies = self.context.cookies()
        with open(COOKIES_PATH, "w", encoding="utf-8") as fh:
            json.dump(cookies, fh, indent=2)
        logger.info("Saved %d cookies.", len(cookies))

    def _load_cookies(self) -> None:
        with open(COOKIES_PATH, "r", encoding="utf-8") as fh:
            cookies = json.load(fh)
        self.context.add_cookies(cookies)
        logger.info("Loaded %d cookies from disk.", len(cookies))

    # ──────────────────────────────────────────
    # Feed Interaction (Watch / Like)
    # ──────────────────────────────────────────
    def interact_feed(self) -> None:
        """Scroll the For-You page, watch videos, and like niche-related
        content to train the algorithm toward the trading niche.
        """
        wait_until_active()
        logger.info("=== FEED INTERACTION ===")

        self.page.goto(TIKTOK_BASE, wait_until="domcontentloaded")
        random_sleep(*DELAY_MEDIUM, page=self.page)

        if handle_challenge(self.page, phase="feed"):
            logger.warning("Challenge on feed page – aborting feed interaction.")
            return
        if not self._ensure_page_has_content("feed", max_retries=2, retry_scroll=True):
            self._mark_soft_block("feed")
            return

        videos_watched = 0
        consecutive_play_errors = 0
        max_consecutive_play_errors = 3
        round_num = 0
        max_rounds = max(FEED_SCROLL_ROUNDS * 2, 25)  # allow extra rounds when skipping broken videos

        while videos_watched < MAX_VIDEOS_TO_WATCH and round_num < max_rounds:
            round_num += 1
            wait_until_active()

            if get_throttle().is_critical:
                logger.warning("Throttle critical – stopping feed early.")
                break

            logger.info(
                "Feed round %d (watched %d/%d videos)",
                round_num, videos_watched, MAX_VIDEOS_TO_WATCH,
            )

            # If current video shows "trouble playing", scroll to next and retry (no count)
            try:
                has_play_error = self.page.evaluate("""() => {
                    const text = (document.body?.innerText || "").toLowerCase();
                    return text.includes("having trouble playing") || text.includes("please refresh");
                }""")
            except Exception:
                has_play_error = False
            if has_play_error:
                consecutive_play_errors += 1
                if consecutive_play_errors >= max_consecutive_play_errors:
                    logger.info(
                        "Multiple playback errors in a row – refreshing feed once."
                    )
                    try:
                        self.page.reload(wait_until="domcontentloaded")
                        random_sleep(4.0, 7.0, page=self.page)
                    except Exception:
                        pass
                    consecutive_play_errors = 0
                else:
                    logger.info("Video playback error – scrolling to next.")
                    try:
                        human_scroll_next_video(self.page)
                    except Exception:
                        pass
                    random_sleep(*DELAY_SHORT, page=self.page)
                continue
            consecutive_play_errors = 0

            # Watch the current video with idle simulation
            watch_duration = random.uniform(
                self._session_behavior["watch_min"],
                self._session_behavior["watch_max"],
            )
            logger.info("Watching video for %.1f s …", watch_duration)
            idle_sleep(self.page, watch_duration)
            videos_watched += 1

            # Decide whether to like
            if self._likes_this_session < MAX_LIKES_PER_SESSION:
                if self._is_niche_content():
                    self._try_like_current_video()
                else:
                    logger.debug("Video not niche-relevant – skipping like.")

            if videos_watched >= MAX_VIDEOS_TO_WATCH:
                break

            # Occasional long pause (human behavior: distracted, reading comments)
            if random.random() < self._session_behavior.get("long_pause_chance", 0.15):
                lp_min, lp_max = self._session_behavior.get("long_pause_range", (15.0, 30.0))
                long_pause = random.uniform(lp_min, lp_max)
                logger.info("Taking a natural break (%.0f s) …", long_pause)
                idle_sleep(self.page, long_pause)

            # Scroll to next video
            human_scroll_next_video(self.page)
            random_sleep(*DELAY_SHORT, page=self.page)
            if not self._ensure_page_has_content("feed", max_retries=1, retry_scroll=False):
                logger.warning("Feed content stopped loading mid-session; ending feed task.")
                self._mark_soft_block("feed-mid-session")
                break

        logger.info(
            "Feed interaction complete. Watched %d videos, liked %d total this session.",
            videos_watched,
            self._likes_this_session,
        )

    def _is_niche_content(self) -> bool:
        """Check if the CURRENTLY VISIBLE video is niche-relevant.

        Instead of checking the entire page body text (which is noisy on
        TikTok's SPA), we target the video description and author elements
        specifically.
        """
        text_parts = []

        # 1. Try video description element
        for desc_sel in [SELECTORS["video_desc"], '[data-e2e="video-desc"]',
                         '[class*="DivVideoInfoContainer"]']:
            try:
                desc = self.page.locator(desc_sel).first
                if desc.is_visible(timeout=1000):
                    text_parts.append(desc.inner_text(timeout=2000).lower())
                    break
            except Exception:
                continue

        # 2. Try to get hashtag links from the current video
        try:
            hashtags = self.page.locator(
                'a[href*="/tag/"], a[data-e2e="search-common-link"]'
            ).all()
            for tag in hashtags[:10]:
                try:
                    tag_text = tag.inner_text(timeout=500).lower()
                    if tag_text:
                        text_parts.append(tag_text)
                except Exception:
                    continue
        except Exception:
            pass

        # 3. Try author name
        try:
            author = self.page.locator(SELECTORS["video_author"]).first
            if author.is_visible(timeout=500):
                text_parts.append(author.inner_text(timeout=1000).lower())
        except Exception:
            pass

        # 4. Fallback: check a limited scope of the page
        if not text_parts:
            try:
                # Get text from the main content area only, not sidebar
                main_area = self.page.locator('[id="main-content-others_homepage"],'
                                              '[class*="DivContentContainer"],'
                                              'main').first
                body_text = main_area.inner_text(timeout=2000).lower()
                text_parts.append(body_text[:2000])  # limit to avoid noise
            except Exception:
                try:
                    body_text = self.page.inner_text("body").lower()
                    text_parts.append(body_text[:2000])
                except Exception:
                    return False

        combined = " ".join(text_parts)
        is_niche = any(kw in combined for kw in NICHE_KEYWORDS)

        if is_niche:
            matching = [kw for kw in NICHE_KEYWORDS if kw in combined]
            logger.debug("Niche match found: %s", matching[:5])

        return is_niche

    def _try_like_current_video(self) -> None:
        """Like the currently-visible video if not already liked.

        Uses multiple strategies to detect if video is already liked,
        and multiple selectors to find the like button.
        """
        try:
            # Find the like button (primary + fallback selectors)
            like_btn = None
            for sel in [SELECTORS["like_button"], SELECTORS.get("like_button_alt", "")]:
                if not sel:
                    continue
                try:
                    btn = self.page.locator(sel).first
                    if btn.is_visible(timeout=1500):
                        like_btn = btn
                        break
                except Exception:
                    continue

            if like_btn is None:
                logger.debug("Like button not found.")
                return

            # Check if already liked using multiple strategies
            already_liked = False

            # Strategy 1: Check active-state selectors
            for check_sel in SELECTORS.get("like_button_active_checks", []):
                try:
                    if element_exists(self.page, check_sel, timeout=500):
                        already_liked = True
                        break
                except Exception:
                    continue

            # Strategy 2: Check the button's color/fill via JS
            if not already_liked:
                try:
                    is_red = self.page.evaluate("""() => {
                        const btn = document.querySelector('[data-e2e="like-icon"]');
                        if (!btn) return false;
                        const svg = btn.querySelector('svg');
                        if (svg) {
                            const fill = svg.getAttribute('fill') || '';
                            const color = window.getComputedStyle(svg).color || '';
                            return fill.includes('254') || fill.includes('FE2C55') ||
                                   color.includes('254') || color.includes('FE2C55');
                        }
                        const style = window.getComputedStyle(btn);
                        return style.color.includes('254') || style.color.includes('FE2C55');
                    }""")
                    if is_red:
                        already_liked = True
                except Exception:
                    pass

            if already_liked:
                logger.debug("Video already liked – skipping.")
                return

            # Click the like button
            human_click_element(self.page, like_btn, timeout=3000)
            self._likes_this_session += 1
            logger.info("Liked a video (total likes this session: %d).", self._likes_this_session)
            random_sleep(*DELAY_SHORT, page=self.page)
            get_throttle().decay(0.1)

        except Exception as exc:
            logger.debug("Could not like video: %s", exc)

    # ──────────────────────────────────────────
    # Mutuals / Network Growth
    # ──────────────────────────────────────────
    def find_mutuals(self, target_hashtag: str | None = None) -> None:
        """The 'Mutuals' growth engine.

        Strategy (CAPTCHA-safe):
        1. FIRST: collect profile links from the For-You feed (no CAPTCHA risk).
        2. ONLY IF feed yields few links: try the target hashtag page.
        3. If hashtag page triggers CAPTCHA, stop — don't try fallbacks.
        4. Visit each profile, check mutual + niche, follow if both match.
        """
        wait_until_active()
        tag = target_hashtag or TARGET_HASHTAG
        logger.info("=== MUTUALS GROWTH (primary: #%s) ===", tag)

        profile_links: list[str] = []
        captcha_hit = False

        # ── Strategy 1: Search via Target Hashtag (Primary) ──
        # This ensures we target the specific niche ("trading") rather than random feed.
        if self._captcha_hit_this_session:
            logger.info("Skipping hashtag search due to prior CAPTCHA.")
        else:
            # Go to home first and pause so hashtag visit looks like "browsed then searched" (reduces CAPTCHA).
            try:
                self.page.goto(TIKTOK_BASE, wait_until="domcontentloaded")
                transition_pause = random.uniform(HASHTAG_TRANSITION_PAUSE_MIN, HASHTAG_TRANSITION_PAUSE_MAX)
                logger.info("Pausing %.0f s before opening #%s (natural transition).", transition_pause, TARGET_HASHTAG)
                random_sleep(transition_pause, transition_pause + 5.0, page=self.page)
            except Exception:
                pass
            logger.info("Searching for niche profiles via #%s …", TARGET_HASHTAG)
            tag_links = self._load_hashtag_profiles(TARGET_HASHTAG)
            
            if tag_links is None:
                 self._captcha_hit_this_session = True
            elif tag_links:
                 logger.info("Found %d profiles from #%s.", len(tag_links), TARGET_HASHTAG)
                 profile_links.extend(tag_links)

        # ── Strategy 2: Fallback to Feed (Secondary) ──
        # Only if we need more profiles or hashtag search failed/yielded few results
        if len(profile_links) < 5 and not self._captcha_hit_this_session:
            logger.info("Collecting additional profiles from For-You feed …")
            try:
                self.page.goto(TIKTOK_BASE, wait_until="domcontentloaded")
                random_sleep(*DELAY_MEDIUM, page=self.page)
                if not handle_challenge(self.page, phase="feed"):
                    scroll_page(self.page, times=random.randint(3, 5))
                    feed_links = self._extract_profile_links()
                    profile_links.extend(feed_links)
                    logger.info("Collected %d additional profile links from feed.", len(feed_links))
                else:
                    self._captcha_hit_this_session = True
            except Exception as e:
                logger.warning("Feed profile extraction error during fallback: %s", e)


        # ── Strategy 2b: Fallback hashtags (ONLY if no CAPTCHA so far) ──
        if (
            len(profile_links) < 3
            and not captcha_hit
            and not self._captcha_hit_this_session
            and not target_hashtag
        ):
            for fallback_tag in FALLBACK_HASHTAGS[:2]:  # max 2 fallbacks
                if self._follows_this_session >= MAX_FOLLOWS_PER_SESSION:
                    break
                logger.info("Trying fallback hashtag #%s …", fallback_tag)
                extra = self._load_hashtag_profiles(fallback_tag)
                if extra is None:
                    captcha_hit = True
                    self._captcha_hit_this_session = True
                    break
                profile_links.extend(extra)
                if len(profile_links) >= 10:
                    break

        if not profile_links:
            logger.warning("No profile links found. Skipping mutuals this session.")
            return

        # Deduplicate
        seen = set()
        unique_links = []
        for link in profile_links:
            normalised = self._normalise_profile_url(link)
            if normalised and normalised not in seen:
                seen.add(normalised)
                unique_links.append(normalised)

        random.shuffle(unique_links)
        max_to_evaluate = min(len(unique_links), 3)
        logger.info("Evaluating %d of %d unique profiles (limited to prevent CAPTCHA).", max_to_evaluate, len(unique_links))

        # Pause naturally before first profile visit.
        pre_profile_pause = random.uniform(20.0, 40.0)
        logger.info("Pausing %.0f s before first profile visit (natural browsing).", pre_profile_pause)
        random_sleep(pre_profile_pause, pre_profile_pause + 5.0, page=self.page)

        for i, link in enumerate(unique_links[:max_to_evaluate]):
            wait_until_active()
            
            # ── DIAGNOSTIC: Log profile visit count ──
            logger.warning(
                "[DIAGNOSTIC] Profile visit #%d in this cycle (max=%d). "
                "Session totals: follows=%d, likes=%d",
                i + 1, max_to_evaluate, self._follows_this_session, self._likes_this_session
            )

            if self._follows_this_session >= MAX_FOLLOWS_PER_SESSION:
                logger.info(
                    "Follow limit reached (%d). Stopping growth cycle.",
                    MAX_FOLLOWS_PER_SESSION,
                )
                break

            if get_throttle().is_critical:
                logger.warning("Throttle critical – stopping mutuals early.")
                break

            if self._captcha_hit_this_session:
                logger.info("CAPTCHA hit – stopping profile visits for this session.")
                break

            # Navigate directly to profile (don't loop back to hashtag —
            # repeated hashtag→profile→hashtag navigation is a bot pattern).
            self._evaluate_and_follow(link)

            # Cooldown between visits — stay on home feed like a real user
            if i < max_to_evaluate - 1:
                try:
                    self.page.goto(TIKTOK_BASE, wait_until="domcontentloaded")
                except Exception:
                    pass
                pause_min, pause_max = self._session_behavior["profile_eval_pause"]
                logger.info("Cooling down %.0f-%.0f s before next profile visit …", pause_min, pause_max)
                random_sleep(pause_min, pause_max, page=self.page)
                # Check for CAPTCHA before next visit
                if handle_challenge(self.page, phase="profile"):
                    self._captcha_hit_this_session = True
                    logger.info("CAPTCHA detected during cooldown — stopping profile visits.")
                    break

        logger.info(
            "Mutuals cycle complete. Follows this session: %d",
            self._follows_this_session,
        )

    def _load_hashtag_profiles(self, tag: str) -> list[str] | None:
        """Find niche profiles by searching for the tag keyword.

        PRIMARY: Use TikTok search (less CAPTCHA-prone than direct tag URLs).
        FALLBACK: Try direct tag URL if search yields nothing.

        Returns a list of links, or None if a CAPTCHA was triggered
        (indicating the caller should stop all hashtag attempts).
        """
        # ── Strategy A: Use TikTok search (safer than tag pages) ──
        search_url = f"{TIKTOK_BASE}/search/user?q={tag}"
        try:
            logger.info("Searching for '%s' users via TikTok search …", tag)
            self.page.goto(search_url, wait_until="domcontentloaded")
        except Exception as e:
            logger.warning("Search page load issue for '%s': %s", tag, e)
            # Fall through to tag URL fallback
            search_url = None

        if search_url:
            time.sleep(random.uniform(3.0, 6.0))
            human_mouse_warmup(self.page)
            human_hashtag_warmup(self.page)

            if handle_challenge(self.page, phase="search"):
                logger.warning("Challenge on search page for '%s'.", tag)
                return None

            # Extract profiles from search results
            links = self._extract_profile_links()
            if links:
                logger.info("Found %d profiles from search for '%s'.", len(links), tag)
                return links

        # ── Strategy B: Fallback to direct tag URL ──
        tag_url = f"{TIKTOK_BASE}/tag/{tag}"
        try:
            logger.info("Falling back to tag page #%s …", tag)
            self.page.goto(tag_url, wait_until="domcontentloaded")
        except Exception as e:
            logger.warning("Hashtag page load issue for #%s: %s", tag, e)
            return []

        time.sleep(random.uniform(3.0, 6.0))
        human_hashtag_warmup(self.page)
        human_mouse_warmup(self.page)

        if handle_challenge(self.page, phase="hashtag"):
            logger.warning("Challenge on tag page #%s.", tag)
            return None  # Signal CAPTCHA to caller
        
        # ── DIAGNOSTIC: Log hashtag page content state ──
        try:
            diag_info = self.page.evaluate("""() => {
                const skeletons = document.querySelectorAll('[class*="skeleton"], [class*="Skeleton"]').length;
                const videos = document.querySelectorAll('[data-e2e="recommend-list-item-container"]').length;
                const profiles = document.querySelectorAll('a[href*="/@"]').length;
                const bodyText = document.body?.innerText || "";
                const hasContent = bodyText.length > 200;
                return { skeletons, videos, profiles, hasContent, bodyLen: bodyText.length };
            }""")
            logger.warning(
                "[DIAGNOSTIC] Hashtag #%s page state: skeletons=%d, videos=%d, profiles=%d, bodyLen=%d, hasContent=%s",
                tag, diag_info.get("skeletons", 0), diag_info.get("videos", 0),
                diag_info.get("profiles", 0), diag_info.get("bodyLen", 0), diag_info.get("hasContent", False)
            )
        except Exception as diag_err:
            logger.debug("[DIAGNOSTIC] Failed to get hashtag page state: %s", diag_err)
        
        if not self._ensure_page_has_content("hashtag", max_retries=2, retry_scroll=True):
            self._mark_soft_block(f"hashtag:{tag}")
            return []

        # Scroll to load more content (limited scrolling to avoid detection)
        scroll_page(self.page, times=random.randint(2, 3))
        if not self._ensure_page_has_content("hashtag", max_retries=1, retry_scroll=True):
            self._mark_soft_block(f"hashtag-post-scroll:{tag}")
            return []

        return self._extract_profile_links()

    def _extract_profile_links(self) -> list[str]:
        """Scrape unique PROFILE URLs from the current page.

        KEY FIX: filters OUT video links (/@user/video/123) and only
        keeps actual profile URLs (/@username or /@username?lang=xx).
        Also extracts author links from video cards.
        """
        links: set[str] = set()

        try:
            anchors = self.page.locator("a[href*='/@']").all()
            for anchor in anchors:
                try:
                    href = anchor.get_attribute("href")
                    if not href or "/@" not in href:
                        continue

                    full_url = href if href.startswith("http") else f"{TIKTOK_BASE}{href}"

                    # CRITICAL: Only keep profile URLs, not video URLs
                    normalised = self._normalise_profile_url(full_url)
                    if normalised:
                        links.add(normalised)
                except Exception:
                    continue

        except Exception as exc:
            logger.warning("Error extracting profile links: %s", exc)

        logger.debug("Extracted %d profile links from page.", len(links))
        return list(links)

    @staticmethod
    def _normalise_profile_url(url: str) -> str | None:
        """Convert any TikTok URL to a clean profile URL, or None if
        the URL is not a profile link.

        Examples:
            /@user/video/123  → None  (video link, skip)
            /@user?lang=en    → https://www.tiktok.com/@user
            /@user            → https://www.tiktok.com/@user
            /@                → None  (empty username)
        """
        if not url or "/@" not in url:
            return None

        # Reject video/photo/live links
        if any(seg in url for seg in ("/video/", "/photo/", "/live/", "/playlist/")):
            return None

        # Extract username from URL
        match = re.search(r"/@([\w.]+)", url)
        if not match:
            return None

        username = match.group(1)
        if not username or len(username) < 2:
            return None

        return f"https://www.tiktok.com/@{username}"

    def _evaluate_and_follow(self, profile_url: str) -> None:
        """Visit a profile, check for MUTUAL connection signals AND
        niche relevance, then follow if conditions are met.

        Mutual detection strategy:
        1. Check for CSS elements that indicate mutual connections
        2. Check profile page text for mutual indicator phrases
        3. Check if the profile is niche-relevant (bio, username, videos)

        Anti-CAPTCHA: Run human warmup (mouse, scroll) BEFORE challenge check
        so the page sees interaction first; reduces slider trigger rate.
        """
        try:
            logger.info("Evaluating: %s", profile_url)
            
            # ── DIAGNOSTIC: Log session state before profile visit ──
            throttle = get_throttle()
            logger.info(
                "[DIAGNOSTIC] Pre-visit state: suspicion=%.1f, captcha_count=%d, "
                "follows_this_session=%d, likes_this_session=%d",
                throttle.suspicion_score, throttle.captcha_count,
                self._follows_this_session, self._likes_this_session
            )
            
            self.page.goto(profile_url, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.0, 4.0))

            human_mouse_warmup(self.page)
            # Warm up FIRST: mimic real reading (mouse, scroll) before any checks.
            human_profile_warmup(self.page)

            if handle_challenge(self.page, phase="profile"):
                self._captcha_hit_this_session = True
                return
            if not self._ensure_page_has_content("profile", max_retries=2, retry_scroll=False):
                logger.info("Profile appears restricted/empty; skipping: %s", profile_url)
                self._mark_soft_block("profile")
                return

            # ── Check niche relevance ──
            is_niche = self._check_profile_niche_relevance()
            if not is_niche:
                logger.debug("Profile not niche-relevant – skipping.")
                return

            # ── Check for mutual connections ──
            has_mutual = self._check_mutual_indicators()

            if has_mutual:
                logger.info("Mutual connection found + niche relevant → following.")
                self._click_follow(profile_url)
            else:
                logger.debug("No mutual indicator found for %s.", profile_url)

        except Exception as exc:
            logger.warning("Error evaluating profile %s: %s", profile_url, exc)

    def _check_profile_niche_relevance(self) -> bool:
        """Check if the current profile page is niche-relevant by examining
        multiple signals: bio, username, recent video titles.
        """
        text_parts = []

        # 1. Check bio text
        for bio_sel in [SELECTORS["bio_text"], '[data-e2e="user-bio"]',
                        'h2[data-e2e="user-subtitle"]']:
            try:
                bio = self.page.locator(bio_sel).first
                if bio.is_visible(timeout=1500):
                    text_parts.append(bio.inner_text(timeout=2000).lower())
                    break
            except Exception:
                continue

        # 2. Check username / display name
        for name_sel in [SELECTORS["user_title"], '[data-e2e="user-title"]',
                         'h1[data-e2e="user-subtitle"]']:
            try:
                name_el = self.page.locator(name_sel).first
                if name_el.is_visible(timeout=1000):
                    text_parts.append(name_el.inner_text(timeout=1000).lower())
                    break
            except Exception:
                continue

        # 3. Check visible video titles / descriptions on profile
        try:
            video_descs = self.page.locator('[data-e2e="user-post-item-desc"],'
                                            '[class*="DivVideoTitle"]').all()
            for vd in video_descs[:5]:
                try:
                    text_parts.append(vd.inner_text(timeout=500).lower())
                except Exception:
                    continue
        except Exception:
            pass

        # 4. Broader fallback: check page text (limited scope)
        if not text_parts:
            try:
                page_text = self.page.inner_text("body").lower()
                text_parts.append(page_text[:3000])
            except Exception:
                return False

        combined = " ".join(text_parts)
        return any(kw in combined for kw in NICHE_KEYWORDS)

    def _check_mutual_indicators(self) -> bool:
        """Check if the current profile has mutual-connection indicators.

        Uses THREE strategies:
        1. CSS selector check for mutual friend elements
        2. Text-based check for mutual phrases in page content
        3. JavaScript-based DOM inspection for hidden mutual elements
        """
        # Strategy 1: CSS selectors for mutual indicator elements
        for sel in SELECTORS.get("mutual_indicator_selectors", []):
            try:
                if element_exists(self.page, sel, timeout=1000):
                    logger.debug("Mutual indicator found via selector: %s", sel)
                    return True
            except Exception:
                continue

        # Strategy 2: Text-based check on the page
        try:
            # Get text from the profile header area (more targeted than full body)
            header_text = ""
            for scope_sel in ['[data-e2e="user-page"]',
                              '[class*="ShareLayoutHeader"]',
                              '[class*="UserInfoContainer"]',
                              'header', 'main']:
                try:
                    scope = self.page.locator(scope_sel).first
                    if scope.is_visible(timeout=1000):
                        header_text = scope.inner_text(timeout=3000).lower()
                        break
                except Exception:
                    continue

            if not header_text:
                header_text = self.page.inner_text("body").lower()[:3000]

            for indicator in SELECTORS["mutual_indicator_texts"]:
                if indicator.lower() in header_text:
                    logger.debug("Mutual indicator text found: '%s'", indicator)
                    return True

        except Exception as e:
            logger.debug("Text-based mutual check error: %s", e)

        # Strategy 3: JS-based check for elements that might not match CSS selectors
        try:
            has_mutual_js = self.page.evaluate("""() => {
                // Look for any element containing mutual/followed-by text
                const selectors = [
                    '[class*="utual"]',
                    '[class*="followedBy"]',
                    '[class*="FollowedBy"]',
                    '[data-e2e*="mutual"]',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.offsetParent !== null) return true;
                }
                // Also check for small text near follow button
                const allText = document.body.innerText.toLowerCase();
                const indicators = ['followed by', 'mutual friend', 'mutual connection', 'friends with'];
                for (const ind of indicators) {
                    if (allText.includes(ind)) return true;
                }
                return false;
            }""")
            if has_mutual_js:
                logger.debug("Mutual indicator found via JS check.")
                return True
        except Exception:
            pass

        return False

    def _click_follow(self, profile_url: str) -> None:
        """Click the Follow button using human-like mouse movement."""
        try:
            follow_btn = None

            # Try primary selector
            for sel in [SELECTORS["follow_button"],
                        SELECTORS.get("follow_button_alt", "")]:
                if not sel:
                    continue
                try:
                    btn = self.page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        follow_btn = btn
                        break
                except Exception:
                    continue

            if follow_btn is None:
                logger.debug("Follow button not found on %s.", profile_url)
                return

            btn_text = follow_btn.inner_text(timeout=3000).strip().lower()

            if btn_text in ("following", "friends", "requested", "follow back"):
                logger.info("Already following/requested %s – skipping.", profile_url)
                return

            if btn_text not in ("follow", ""):
                logger.debug("Follow button text unexpected: '%s' – skipping.", btn_text)
                return

            human_click_element(self.page, follow_btn, timeout=5000)
            self._follows_this_session += 1
            logger.info(
                "Followed %s (session total: %d/%d).",
                profile_url,
                self._follows_this_session,
                MAX_FOLLOWS_PER_SESSION,
            )
            random_sleep(*DELAY_MEDIUM, page=self.page)
            get_throttle().decay(0.1)

        except Exception as exc:
            logger.warning("Could not click Follow on %s: %s", profile_url, exc)

    # ──────────────────────────────────────────
    # Suggested Accounts (alternative growth)
    # ──────────────────────────────────────────
    def process_suggested_accounts(self) -> None:
        """Inspect the 'Suggested Accounts' sidebar and follow niche-
        relevant users with mutual indicators.

        Tries multiple selectors since TikTok redesigns the sidebar
        frequently. Includes delay and CAPTCHA checks to reduce slider triggers.
        """
        wait_until_active()
        logger.info("=== SUGGESTED ACCOUNTS ===")

        self.page.goto(TIKTOK_BASE, wait_until="domcontentloaded")
        random_sleep(*DELAY_MEDIUM, page=self.page)

        if handle_challenge(self.page, phase="suggested"):
            self._captcha_hit_this_session = True
            return

        # Pause before interacting with sidebar (reduces CAPTCHA on profile visits)
        pause = random.uniform(12.0, 22.0)
        logger.info("Pausing %.0f s before suggested accounts (natural browsing).", pause)
        random_sleep(pause, pause + 3.0, page=self.page)
        if handle_challenge(self.page):
            self._captcha_hit_this_session = True
            return

        # Try multiple selectors for the suggested accounts section
        suggested = None
        for sel in SELECTORS.get("suggested_accounts_selectors", []):
            try:
                loc = self.page.locator(sel)
                if element_exists(self.page, sel, timeout=3000):
                    suggested = loc.first
                    logger.info("Found suggested accounts via: %s", sel)
                    break
            except Exception:
                continue

        if suggested is None:
            logger.info("Suggested accounts sidebar not found (tried all selectors).")
            # Fallback: try to find user recommendation cards anywhere on page
            try:
                self._process_any_visible_suggestions()
            except Exception as e:
                logger.debug("Fallback suggestion processing failed: %s", e)
            return

        try:
            user_cards = suggested.locator(SELECTORS["user_card"]).all()
            if not user_cards:
                # Try broader card selector
                user_cards = suggested.locator("a[href*='/@']").all()

            logger.info("Found %d suggested user cards.", len(user_cards))
            suggested_follows_this_task = 0

            for card in user_cards:
                if self._follows_this_session >= MAX_FOLLOWS_PER_SESSION:
                    break
                if suggested_follows_this_task >= MAX_SUGGESTED_FOLLOWS:
                    logger.info("Reached suggested-account follow limit (%d).", MAX_SUGGESTED_FOLLOWS)
                    break
                if get_throttle().is_critical:
                    logger.warning("Throttle critical – stopping suggested accounts.")
                    break
                if handle_challenge(self.page):
                    self._captcha_hit_this_session = True
                    break

                try:
                    desc_text = card.inner_text(timeout=2000).lower()
                    is_niche = any(kw in desc_text for kw in NICHE_KEYWORDS)
                    has_mutual = any(
                        ind.lower() in desc_text
                        for ind in SELECTORS["mutual_indicator_texts"]
                    )

                    if is_niche and has_mutual:
                        follow_btn = card.locator(SELECTORS["follow_button"]).first
                        human_click_element(self.page, follow_btn, timeout=3000)
                        self._follows_this_session += 1
                        suggested_follows_this_task += 1
                        logger.info(
                            "Followed suggested account (total: %d).",
                            self._follows_this_session,
                        )
                        random_sleep(*DELAY_MEDIUM, page=self.page)
                        get_throttle().decay(0.1)
                    elif is_niche:
                        logger.debug("Suggested card niche-relevant but no mutual indicator.")
                except Exception as inner_exc:
                    logger.debug("Skipping suggested card: %s", inner_exc)

        except Exception as exc:
            logger.warning("Error processing suggested accounts: %s", exc)

    def _process_any_visible_suggestions(self) -> None:
        """Fallback: look for any recommendation/suggestion links on the
        current page and evaluate them for follow.
        """
        try:
            # Look for "See all" or "View more" type links that expand suggestions
            expand_selectors = [
                'text="See all"',
                'text="View all"',
                '[data-e2e="see-all"]',
            ]
            for sel in expand_selectors:
                try:
                    btn = self.page.locator(sel).first
                    if btn.is_visible(timeout=1000):
                        human_click_element(self.page, btn, timeout=2000)
                        random_sleep(*DELAY_SHORT, page=self.page)
                        break
                except Exception:
                    continue

            # Now extract any visible user links from the page
            user_links = self._extract_profile_links()
            random.shuffle(user_links)
            # Limit profile visits to reduce CAPTCHA (suggested flow is high-risk)
            max_suggested_profiles = 2
            for link in user_links[:max_suggested_profiles]:
                if self._follows_this_session >= MAX_FOLLOWS_PER_SESSION:
                    break
                if self._captcha_hit_this_session:
                    logger.info("CAPTCHA hit – stopping profile visits.")
                    break
                random_sleep(15.0, 25.0, page=self.page)
                if handle_challenge(self.page, phase="suggested"):
                    self._captcha_hit_this_session = True
                    break
                self._evaluate_and_follow(link)

        except Exception as e:
            logger.debug("_process_any_visible_suggestions error: %s", e)

    # ──────────────────────────────────────────
    # Video Upload
    # ──────────────────────────────────────────
    def upload_content(self, video_path: str, caption: str) -> bool:
        """Upload a video to TikTok with the given caption.

        Returns ``True`` on apparent success, ``False`` otherwise.
        """
        wait_until_active()
        video_path = os.path.abspath(video_path)

        if not os.path.isfile(video_path):
            logger.error("Video file not found: %s", video_path)
            return False

        logger.info("=== UPLOADING VIDEO: %s ===", video_path)

        self.page.goto(TIKTOK_UPLOAD, wait_until="domcontentloaded")
        random_sleep(*DELAY_LONG, page=self.page)

        if handle_challenge(self.page, phase="upload"):
            logger.warning("Challenge on upload page – aborting.")
            return False

        try:
            # TikTok upload page uses an iframe — find the correct one by src
            frame = None
            for iframe_sel in [
                'iframe[src*="creator"]',
                'iframe[src*="upload"]',
                SELECTORS["upload_iframe"],  # generic "iframe" fallback
            ]:
                try:
                    iframe_loc = self.page.locator(iframe_sel).first
                    if iframe_loc.is_visible(timeout=5000):
                        f = iframe_loc.content_frame()
                        if f is not None:
                            frame = f
                            logger.info("Upload iframe found via selector: %s", iframe_sel)
                            break
                except Exception:
                    continue

            target = frame if frame else self.page

            # Wait for the file input to be ready before interacting
            logger.info("Waiting for upload file input …")
            try:
                target.locator(SELECTORS["upload_file_input"]).first.wait_for(
                    state="visible", timeout=30000
                )
            except Exception as wait_err:
                logger.warning("File input wait timed out: %s — proceeding anyway.", wait_err)

            # Handle file chooser
            logger.info("Selecting video file …")
            file_input = target.locator(SELECTORS["upload_file_input"]).first
            file_input.set_input_files(video_path)
            logger.info("File selected. Waiting for upload processing …")
            random_sleep(*DELAY_LONG, page=self.page)

            # Wait extra time for video to process
            idle_sleep(self.page, random.uniform(10.0, 20.0))

            # Type caption — try the specific caption editor first, then fallback
            logger.info("Typing caption …")
            try:
                caption_el = None
                for cap_sel in [SELECTORS["caption_editor"], SELECTORS["caption_input"]]:
                    try:
                        el = target.locator(cap_sel).first
                        if el.is_visible(timeout=4000):
                            caption_el = el
                            logger.info("Caption element found via: %s", cap_sel)
                            break
                    except Exception:
                        continue
                if caption_el is None:
                    caption_el = target.locator(SELECTORS["caption_input"]).first

                try:
                    caption_el.click(timeout=5000)
                except Exception:
                    pass
                random_sleep(0.5, 1.0)

                # Clear existing text
                select_all = "Meta+A" if platform.system() == "Darwin" else "Control+A"
                self.page.keyboard.press(select_all)
                random_sleep(0.2, 0.4)
                self.page.keyboard.press("Backspace")
                random_sleep(0.3, 0.6)

                try:
                    caption_el.type(caption, delay=random.randint(50, 150))
                except Exception:
                    self.page.keyboard.type(caption, delay=random.randint(50, 150))
            except Exception as cap_exc:
                logger.warning("Caption typing via element failed: %s. Trying keyboard.", cap_exc)
                self.page.keyboard.type(caption, delay=random.randint(50, 150))

            random_sleep(*DELAY_MEDIUM, page=self.page)

            # Click Post
            logger.info("Clicking Post button …")
            post_clicked = False
            for post_sel in [SELECTORS["post_button"],
                             SELECTORS.get("post_button_alt", "")]:
                if not post_sel:
                    continue
                try:
                    post_btn = target.locator(post_sel).first
                    if post_btn.is_visible(timeout=5000):
                        post_btn.click(timeout=10000)
                        post_clicked = True
                        break
                except Exception:
                    continue

            if not post_clicked:
                try:
                    target.locator(SELECTORS["post_button"]).first.click(timeout=10000)
                    post_clicked = True
                except Exception as exc:
                    logger.warning("Fallback Post click failed: %s", exc)

            if not post_clicked:
                logger.error("Could not click the Post button.")
                return False

            logger.info("Post button clicked. Waiting for confirmation …")
            random_sleep(*DELAY_LONG, page=self.page)

            # Verify success
            idle_sleep(self.page, random.uniform(5.0, 10.0))
            current_url = self.page.url

            # Check multiple success indicators
            for success_sel in SELECTORS.get("upload_success_indicators", []):
                try:
                    if element_exists(target, success_sel, timeout=5000) or element_exists(self.page, success_sel, timeout=5000):
                        logger.info("Upload success indicator found: %s", success_sel)
                        return True
                except Exception:
                    continue

            if "upload" not in current_url.lower():
                logger.info("Redirected away from upload page – video likely posted.")
                return True

            logger.warning("Could not confirm upload success – please verify manually.")
            return False

        except Exception as exc:
            logger.error("Upload failed: %s", exc)
            return False

    # ──────────────────────────────────────────
    # Video Scheduling
    # ──────────────────────────────────────────
    def check_and_upload_scheduled(self) -> None:
        """Check if any scheduled videos are due and upload them."""
        if not os.path.isfile(SCHEDULE_FILE):
            return

        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as fh:
                schedules = json.load(fh)
        except (json.JSONDecodeError, IOError):
            return

        if not schedules:
            return

        from datetime import datetime
        now = datetime.now()
        remaining = []
        uploaded_any = False

        for entry in schedules:
            scheduled_time = datetime.fromisoformat(entry["scheduled_time"])
            if now >= scheduled_time and entry.get("status") != "done":
                logger.info("Scheduled upload due: %s", entry["video_path"])
                wait_until_active()
                success = self.upload_content(entry["video_path"], entry["caption"])
                entry["status"] = "done" if success else "failed"
                entry["attempted_at"] = now.isoformat()
                uploaded_any = True
            remaining.append(entry)

        if uploaded_any:
            with open(SCHEDULE_FILE, "w", encoding="utf-8") as fh:
                json.dump(remaining, fh, indent=2)

    # ──────────────────────────────────────────
    # Composite Session Runner
    # ──────────────────────────────────────────
    def run_session(self) -> None:
        """Execute a full bot session.

        Strategy: ALWAYS run feed interaction first (CAPTCHA-safe), then
        only run profile-visit tasks (mutuals, suggested) if no CAPTCHA
        was triggered.  This protects new accounts that get heavily
        CAPTCHA'd on any navigation beyond feed scrolling.
        """
        wait_until_active()
        logger.info("========== SESSION START ==========")

        # Reset per-session counters
        self._follows_this_session = 0
        self._likes_this_session = 0
        self._captcha_hit_this_session = False
        self._content_blocked_this_session = False
        self._session_behavior = self._build_session_behavior()

        # Check for scheduled uploads first
        try:
            self.check_and_upload_scheduled()
        except Exception as e:
            logger.warning("Scheduled upload check failed: %s", e)

        try:
            # ── PHASE 1: Always run feed interaction first (safe) ──
            wait_until_active()
            logger.info("Starting task: feed")
            self.interact_feed()
            random_sleep(*DELAY_LONG, page=self.page)

            # ── PHASE 2: Profile-visit tasks (order: mutuals then suggested) ──
            # Order: feed (scroll) → mutuals (#trading + profiles) → suggested.
            # Isolation: set ENABLE_MUTUALS=False or ENABLE_SUGGESTED=False in config to test CAPTCHA source.
            profile_tasks = []
            if ENABLE_MUTUALS:
                profile_tasks.append(("mutuals", self.find_mutuals))
            if ENABLE_SUGGESTED:
                profile_tasks.append(("suggested", self.process_suggested_accounts))
            for name, task_fn in profile_tasks:
                if self._captcha_hit_this_session:
                    logger.info("Skipping '%s' – CAPTCHA triggered earlier.", name)
                    continue
                if get_throttle().is_critical:
                    logger.warning("Throttle critical – skipping remaining tasks.")
                    break
                wait_until_active()
                logger.info("Starting task: %s", name)
                task_fn()
                random_sleep(*DELAY_LONG, page=self.page)

        except Exception as exc:
            logger.error("Session error: %s", exc)
        finally:
            logger.info(
                "========== SESSION END (likes: %d, follows: %d) ==========",
                self._likes_this_session,
                self._follows_this_session,
            )
