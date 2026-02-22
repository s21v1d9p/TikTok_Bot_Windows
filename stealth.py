"""
stealth.py – Advanced anti-detection layer for TikTok Browser Bot.

Provides:
- Bézier-curve mouse movement (natural pointer paths)
- Human-like clicking with offset jitter
- Idle simulation (micro-movements during wait periods)
- CAPTCHA / rate-limit detection with adaptive throttling
- Browser fingerprint hardening scripts
- Viewport randomisation
"""

from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass, field

from bot_utils import element_exists

logger = logging.getLogger("TikTokBot")

# ──────────────────────────────────────────────
# Adaptive Throttle State
# ──────────────────────────────────────────────

@dataclass
class ThrottleState:
    """Tracks suspicion signals and scales delays accordingly."""
    suspicion_score: float = 0.0
    captcha_count: int = 0
    rate_limit_count: int = 0
    last_action_ts: float = field(default_factory=time.time)

    # Score thresholds
    WARN_THRESHOLD: float = 3.0
    CRITICAL_THRESHOLD: float = 6.0
    MAX_SCORE: float = 10.0

    def bump(self, amount: float = 1.0, reason: str = "") -> None:
        """Increase suspicion score."""
        self.suspicion_score = min(self.suspicion_score + amount, self.MAX_SCORE)
        if reason:
            logger.warning(
                "[Throttle] Suspicion +%.1f (%s) → total %.1f",
                amount, reason, self.suspicion_score,
            )

    def decay(self, amount: float = 0.3) -> None:
        """Gradually reduce suspicion after clean actions."""
        self.suspicion_score = max(0.0, self.suspicion_score - amount)

    @property
    def delay_multiplier(self) -> float:
        """Returns a multiplier (1.0–4.0) to scale all delays."""
        if self.suspicion_score >= self.CRITICAL_THRESHOLD:
            return 4.0
        if self.suspicion_score >= self.WARN_THRESHOLD:
            return 2.0 + (self.suspicion_score - self.WARN_THRESHOLD) * 0.5
        return 1.0 + self.suspicion_score * 0.15

    @property
    def is_critical(self) -> bool:
        return self.suspicion_score >= self.CRITICAL_THRESHOLD

    def record_action(self) -> None:
        self.last_action_ts = time.time()


_throttle = ThrottleState()


def get_throttle() -> ThrottleState:
    """Return the global throttle state."""
    return _throttle


# ──────────────────────────────────────────────
# Bézier Curve Mouse Movement
# ──────────────────────────────────────────────

def _bezier_point(t: float, p0: tuple, p1: tuple, p2: tuple, p3: tuple) -> tuple:
    """Evaluate a cubic Bézier curve at parameter *t* ∈ [0, 1]."""
    u = 1 - t
    x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
    y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
    return (x, y)


def _generate_bezier_path(
    start: tuple[float, float],
    end: tuple[float, float],
    steps: int | None = None,
) -> list[tuple[float, float]]:
    """Generate a natural-looking mouse path from *start* to *end* using
    a cubic Bézier curve with randomised control points.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.hypot(dx, dy)

    if steps is None:
        steps = max(12, int(dist / 8))
    steps = min(steps, 80)

    # Control points: offset perpendicular to the direct line
    spread = max(30, dist * 0.3)
    cp1 = (
        start[0] + dx * random.uniform(0.15, 0.45) + random.uniform(-spread, spread) * 0.3,
        start[1] + dy * random.uniform(0.15, 0.45) + random.uniform(-spread, spread) * 0.3,
    )
    cp2 = (
        start[0] + dx * random.uniform(0.55, 0.85) + random.uniform(-spread, spread) * 0.25,
        start[1] + dy * random.uniform(0.55, 0.85) + random.uniform(-spread, spread) * 0.25,
    )

    path = []
    for i in range(steps + 1):
        t = i / steps
        # Apply easing: slow start, fast middle, slow end
        t_eased = t * t * (3 - 2 * t)  # smoothstep
        pt = _bezier_point(t_eased, start, cp1, cp2, end)
        # Add micro-jitter (±1 px)
        jx = pt[0] + random.uniform(-0.8, 0.8)
        jy = pt[1] + random.uniform(-0.8, 0.8)
        path.append((jx, jy))

    return path


def human_move_mouse(page, target_x: float, target_y: float) -> None:
    """Move the mouse from its current position to (*target_x*, *target_y*)
    along a natural Bézier-curve path with variable speed.
    """
    try:
        # Get current mouse position via JS (fallback to random viewport pos)
        current = page.evaluate(
            "() => ({ x: (window.__mPos && window.__mPos.x) || 0, y: (window.__mPos && window.__mPos.y) || 0 })"
        )
        start = (current.get("x", random.randint(100, 600)),
                 current.get("y", random.randint(100, 400)))
    except Exception:
        start = (random.randint(100, 600), random.randint(100, 400))

    path = _generate_bezier_path(start, (target_x, target_y))

    for px, py in path:
        page.mouse.move(px, py)
        # Variable inter-step delay: faster in middle, slower at ends
        time.sleep(random.uniform(0.003, 0.018))

    # Track position for next call (stored in closure, not on window)
    try:
        page.evaluate(
            f"() => {{ if(!window.__mPos)Object.defineProperty(window,'__mPos',{{value:{{}},writable:true,enumerable:false,configurable:false}}); window.__mPos.x={target_x}; window.__mPos.y={target_y}; }}"
        )
    except Exception:
        pass


def human_click_element(page, locator, timeout: int = 5000) -> bool:
    """Move mouse to *locator* with a Bézier path, then click with a
    slight random offset from center. Returns True on success.
    """
    try:
        locator.wait_for(state="visible", timeout=timeout)
        box = locator.bounding_box(timeout=timeout)
        if not box:
            logger.debug("human_click_element: no bounding box, falling back to direct click")
            locator.click(timeout=timeout)
            return True

        # Target a random point within the element (not dead center)
        offset_x = random.uniform(box["width"] * 0.2, box["width"] * 0.8)
        offset_y = random.uniform(box["height"] * 0.25, box["height"] * 0.75)
        target_x = box["x"] + offset_x
        target_y = box["y"] + offset_y

        human_move_mouse(page, target_x, target_y)
        time.sleep(random.uniform(0.05, 0.2))

        page.mouse.click(target_x, target_y)
        return True

    except Exception as exc:
        logger.debug("human_click_element failed: %s", exc)
        try:
            locator.click(timeout=timeout)
            return True
        except Exception:
            return False


# ──────────────────────────────────────────────
# Idle Simulation
# ──────────────────────────────────────────────

def idle_sleep(page, duration: float) -> None:
    """Sleep for *duration* seconds while performing occasional
    micro-mouse-movements and tiny scrolls to simulate an idle user.
    """
    throttle = get_throttle()
    duration *= throttle.delay_multiplier

    # Cache viewport size once (avoids repeated evaluate() calls)
    try:
        vp = page.viewport_size or {}
        vw = vp.get("width", 1280)
        vh = vp.get("height", 800)
    except Exception:
        vw, vh = 1280, 800

    end_time = time.time() + duration
    while time.time() < end_time:
        remaining = end_time - time.time()
        if remaining <= 0:
            break

        # Decide what to do in this micro-interval
        action_roll = random.random()

        if action_roll < 0.10 and remaining > 1.5:
            # Micro mouse drift (small random movement) – less frequent
            try:
                nx = random.uniform(vw * 0.1, vw * 0.9)
                ny = random.uniform(vh * 0.1, vh * 0.9)
                page.mouse.move(nx, ny)
            except Exception:
                pass
            time.sleep(random.uniform(0.5, 1.5))

        elif action_roll < 0.13 and remaining > 1.0:
            # Tiny scroll (1-3 notches) – less frequent
            try:
                page.mouse.wheel(0, random.choice([-30, -15, 15, 30]))
            except Exception:
                pass
            time.sleep(random.uniform(0.4, 0.8))

        else:
            # Just wait a bit (longer chunks = fewer loop iterations = fewer potential JS calls)
            chunk = min(random.uniform(2.0, 5.0), remaining)
            time.sleep(chunk)


# ──────────────────────────────────────────────
# Enhanced Typing
# ──────────────────────────────────────────────

def human_type_advanced(page, locator, text: str) -> None:
    """Type *text* with realistic rhythm: burst-type within words,
    longer pauses at word boundaries and punctuation.
    """
    try:
        human_click_element(page, locator)
    except Exception:
        locator.click()
    time.sleep(random.uniform(0.3, 0.7))

    for i, char in enumerate(text):
        locator.type(char, delay=0)

        # Determine delay based on context
        if char in (" ", "\n", "\t"):
            # Word boundary — longer pause
            time.sleep(random.uniform(0.10, 0.30))
        elif char in (".", ",", "!", "?", ";", ":"):
            # Punctuation — slight pause
            time.sleep(random.uniform(0.12, 0.35))
        elif char == "#":
            # Hashtag start — brief hesitation
            time.sleep(random.uniform(0.15, 0.40))
        else:
            # Normal keystroke — fast burst
            time.sleep(random.uniform(0.03, 0.12))

        # Occasional longer pause (thinking)
        if random.random() < 0.03:
            time.sleep(random.uniform(0.4, 1.2))

    time.sleep(random.uniform(0.3, 0.8))


# ──────────────────────────────────────────────
# Smooth Scrolling
# ──────────────────────────────────────────────

def smooth_scroll(page, direction: str, distance: int, steps: int = None) -> None:
    """Scroll smoothly using small mouse wheel events.

    Optimized for fluidity (higher event rate) to avoid visual stuttering.
    """
    if steps is None:
        # Steps based on distance but ensuring smoothness
        # Target ~15-25px per step for fluid motion
        steps = max(10, int(distance / 20))
    
    # Randomize step sizes slightly for human variance
    step_amounts = []
    remaining = distance
    for _ in range(steps - 1):
        # Average step size around distance/steps
        avg = remaining / (steps - len(step_amounts))
        amt = int(random.gauss(avg, avg * 0.2)) # Gaussian variance
        amt = max(1, amt)
        step_amounts.append(amt)
        remaining -= amt
    step_amounts.append(remaining)

    sign = 1 if direction == "down" else -1
    
    # Perform the scroll with very short delays for high frame rate (~60fps target)
    for amt in step_amounts:
        page.mouse.wheel(0, sign * amt)
        # Sleep 5-12ms per event -> ~80-160 events/sec (very smooth)
        time.sleep(random.uniform(0.005, 0.012))

    # Small pause after scroll completes
    time.sleep(random.uniform(0.3, 0.7))


def human_scroll_next_video(page) -> None:
    """Advance to the next feed item using TikTok's native snap scroll.

    TikTok's For-You page uses CSS scroll-snap, so keyboard ArrowDown
    cleanly triggers a snap-to-next-video transition.  Avoid many tiny
    mouse.wheel events which fight the snap and cause choppiness.
    """
    try:
        mode = random.choices(
            ["key", "wheel", "mixed"],
            weights=[0.65, 0.20, 0.15],
            k=1,
        )[0]

        if mode == "key":
            # ArrowDown triggers TikTok's native snap-to-next
            page.keyboard.press("ArrowDown")
            time.sleep(random.uniform(0.3, 0.6))

        elif mode == "wheel":
            # Single large wheel event — TikTok snaps to the next video
            vp = page.viewport_size
            distance = (vp["height"] if vp else 800) * random.uniform(0.85, 1.0)
            page.mouse.wheel(0, int(distance))
            time.sleep(random.uniform(0.4, 0.8))

        else:  # mixed
            # Keyboard snap + small settling wheel
            page.keyboard.press("ArrowDown")
            time.sleep(random.uniform(0.3, 0.5))
            page.mouse.wheel(0, random.randint(20, 60))
            time.sleep(random.uniform(0.2, 0.4))

        # Occasional tiny correction (human-like)
        if random.random() < 0.10:
            page.mouse.wheel(0, random.randint(-40, -15))
            time.sleep(random.uniform(0.2, 0.4))

    except Exception:
        try:
            page.keyboard.press("ArrowDown")
        except Exception:
            pass

    time.sleep(random.uniform(0.6, 1.2))


def human_profile_warmup(page) -> None:
    """Simulate brief profile reading behavior before taking actions."""
    # Initial read pause.
    idle_sleep(page, random.uniform(1.0, 2.5))

    # Hover likely interactive profile elements.
    hover_selectors = [
        '[data-e2e="user-title"]',
        '[data-e2e="follow-button"]',
        'a[href*="/video/"]',
        '[data-e2e="followers-count"]',
    ]
    random.shuffle(hover_selectors)

    for sel in hover_selectors[: random.randint(1, 3)]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=800):
                box = el.bounding_box(timeout=1200)
                if box:
                    tx = box["x"] + random.uniform(box["width"] * 0.25, box["width"] * 0.75)
                    ty = box["y"] + random.uniform(box["height"] * 0.25, box["height"] * 0.75)
                    human_move_mouse(page, tx, ty)
                    time.sleep(random.uniform(0.2, 0.7))
        except Exception:
            continue

    # Tiny read scroll pattern.
    try:
        smooth_scroll(page, direction="down", distance=random.randint(120, 420))
        if random.random() < 0.35:
            smooth_scroll(page, direction="up", distance=random.randint(60, 180))
    except Exception:
        pass

    idle_sleep(page, random.uniform(0.6, 1.5))


def human_hashtag_warmup(page) -> None:
    """Simulate brief browsing on a hashtag/tag page before scraping.
    Reduces CAPTCHA by showing human-like activity before DOM queries.
    """
    idle_sleep(page, random.uniform(1.5, 3.0))
    try:
        smooth_scroll(page, direction="down", distance=random.randint(80, 250))
        idle_sleep(page, random.uniform(1.0, 2.5))
    except Exception:
        pass


def human_mouse_warmup(page, steps: int = 18) -> None:
    """Small-step jittered mouse move to a random point in viewport.
    Call before sensitive actions (hashtag load, profile load) to show interaction.
    Sync version for Playwright sync_api.
    """
    try:
        viewport = page.viewport_size or {"width": 1280, "height": 720}
        w, h = viewport.get("width", 1280), viewport.get("height", 720)
        # Target: random point in center 60% of viewport
        tx = w * (0.2 + random.uniform(0, 0.6))
        ty = h * (0.2 + random.uniform(0, 0.6))
        start = page.evaluate("""() => ({ x: window.innerWidth / 2, y: window.innerHeight / 2 })""")
        sx, sy = start.get("x", w / 2), start.get("y", h / 2)
        for i in range(1, steps + 1):
            t = i / steps
            # Slight curve (not linear) for realism
            jx = 0.08 * math.sin(t * math.pi * 2)
            jy = 0.05 * math.cos(t * math.pi * 2)
            cx = sx + (tx - sx) * (t + jx)
            cy = sy + (ty - sy) * (t + jy)
            page.mouse.move(cx, cy, steps=1)
            time.sleep(random.uniform(0.008, 0.022))
        time.sleep(random.uniform(0.3, 0.9))
    except Exception:
        pass


# ──────────────────────────────────────────────
# CAPTCHA & Rate-Limit Detection
# ──────────────────────────────────────────────

CAPTCHA_INDICATORS = [
    "verify you are human",
    "verify your identity",
    "security verification",
    "slide to verify",
    "drag the slider",
    "fit the puzzle",
    "fix the puzzle",
    "captcha",
    "unusual activity",
    "too many requests",
    "try again later",
    "temporarily unavailable",
    "access denied",
    "rate limit",
    "select 2 objects",
    "select the image",
]

CAPTCHA_SELECTORS = [
    '[data-e2e="captcha-verify-container"]',
    '[ID="captcha_container"]',
    'iframe[src*="captcha"]',
    '[class*="tiktok-verify"]',
    '[class*="secsdk-captcha"]',
    # TikTok slider puzzle modal (ByteDance secsdk)
    '[class*="secsdk"]',
    'div[role="dialog"][class*="Verify"]',
    '[class*="Verify"] [class*="modal"]',
    # Specific CAPTCHA button/element selectors (NOT generic disabled buttons)
    'button[class*="captcha"]',
    'button[class*="secsdk"]',
    '[class*="puzzle"]',
    '[class*="drag-icon"]',
    # Specific ID for TikTok slider CAPTCHA
    '#captcha_slide_button',
    'button#captcha_slide_button',
    # Class patterns from actual TikTok CAPTCHA
    '[class*="secsdk-captcha-drag-icon"]',
    'button[class*="secsdk-captcha"]',
]

# Selectors that indicate a legitimate dialog (NOT a CAPTCHA)
LEGITIMATE_DIALOG_SELECTORS = [
    '[data-e2e="login-button"]',  # Login prompt
    '[data-e2e="signup-button"]',  # Signup prompt
    'button:has-text("Log in")',
    'button:has-text("Sign up")',
]


def _detect_captcha_in_shadow_dom(page) -> str | None:
    """Check for CAPTCHA elements inside shadow DOM.
    
    TikTok's CAPTCHA may be rendered inside shadow DOM which normal
    Playwright selectors can't reach.
    """
    try:
        # Use JavaScript to traverse shadow DOM
        result = page.evaluate("""() => {
            // Function to recursively search shadow DOM
            function searchShadowRoot(root, depth = 0) {
                if (depth > 5) return null; // Limit recursion depth
                
                // Check for CAPTCHA elements (specific patterns only — avoid broad matches
                // like "slider" which match TikTok's upload progress bar)
                const captchaSelectors = [
                    '[class*="secsdk-captcha"]',
                    '[class*="captcha"]',
                    '#captcha_slide_button',
                    'button[aria-disabled="true"][class*="secsdk"]',
                    '[class*="drag-icon"]',
                    '[class*="puzzle"]'
                ];
                
                for (const sel of captchaSelectors) {
                    const el = root.querySelector(sel);
                    if (el) {
                        return {
                            found: true,
                            selector: sel,
                            html: el.outerHTML.substring(0, 300),
                            tagName: el.tagName,
                            className: el.className
                        };
                    }
                }
                
                // Search shadow roots
                const allElements = root.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.shadowRoot) {
                        const result = searchShadowRoot(el.shadowRoot, depth + 1);
                        if (result) return result;
                    }
                }
                
                return null;
            }
            
            // Start search from document
            return searchShadowRoot(document);
        }""")
        
        if result and result.get('found'):
            logger.warning(
                "[SHADOW DOM CAPTCHA] Found: %s, class=%s, html=%s...",
                result.get('selector'), result.get('className', '')[:50], result.get('html', '')[:100]
            )
            return f"shadow_dom:{result.get('selector')}"
    except Exception as e:
        logger.debug("[SHADOW DOM] Error searching shadow DOM: %s", e)
    
    return None


def detect_challenge(page, phase: str | None = None) -> str | None:
    """Check if the current page shows a CAPTCHA or rate-limit challenge.

    Returns a description string if a challenge is detected, or None.
    phase: Optional label (feed, hashtag, profile, upload, etc.) to gate
           phase-specific detection logic and avoid false positives.
    """
    try:
        # Check URL-based redirects
        url = page.url.lower()
        if "captcha" in url or "challenge" in url:
             return f"challenge_url:{url}"

        # ── Check shadow DOM for CAPTCHA elements ──
        shadow_result = _detect_captcha_in_shadow_dom(page)
        if shadow_result:
            return shadow_result

        # ── Check for CAPTCHA dialogs on profile pages only ──
        # Skip this check on upload pages — TikTok's upload UI uses dialogs
        # for normal functionality (topic selection, duet settings, etc.) which
        # would otherwise cause false-positive CAPTCHA detection.
        if phase != "upload":
            try:
                dialog = page.locator('div[role="dialog"]').first
                if dialog.is_visible(timeout=300):
                    # Check if this is a legitimate dialog (login/signup prompt)
                    is_legitimate = False
                    for legit_sel in LEGITIMATE_DIALOG_SELECTORS:
                        try:
                            if page.locator(legit_sel).first.is_visible(timeout=200):
                                is_legitimate = True
                                break
                        except Exception:
                            continue

                    if not is_legitimate:
                        # Check dialog content for explicit CAPTCHA keywords only
                        try:
                            dialog_text = dialog.inner_text(timeout=500).lower()
                            dialog_html = dialog.evaluate("el => el.outerHTML")[:500]

                            logger.debug(
                                "[CAPTCHA DETECTION] Dialog found (phase=%s). Text: %s...",
                                phase or "unknown", dialog_text[:100],
                            )

                            captcha_keywords = ["slider", "puzzle", "drag", "verify", "captcha", "fit", "rotate"]
                            for keyword in captcha_keywords:
                                if keyword in dialog_text or keyword in dialog_html.lower():
                                    return f"dialog_captcha:{keyword}"

                            # Only flag as suspicious on profile pages — elsewhere
                            # dialogs are normal UI (settings, terms, tooltips, etc.)
                            if "/@" in url and "search" not in url:
                                logger.warning(
                                    "[CAPTCHA DETECTION] Unexpected dialog on profile page - treating as CAPTCHA"
                                )
                                return "unexpected_dialog_on_profile"
                        except Exception as e:
                            logger.debug("[CAPTCHA DETECTION] Error checking dialog content: %s", e)
            except Exception:
                pass

        # Check for CAPTCHA DOM elements
        for sel in CAPTCHA_SELECTORS:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=500):
                    # Log what we found to debug false positives
                    try:
                        html_snippet = el.evaluate("el => el.outerHTML")[:200]
                        logger.warning("Potential CAPTCHA element found (%s): %s", sel, html_snippet)
                    except Exception:
                        pass
                    return f"captcha_element:{sel}"
            except Exception:
                continue

        # Check page text for rate-limit language
        # Only check specific error containers, not entire body (too slow & noisy)
        try:
            # Common error containers
            for container in ['[data-e2e="error-page"]', 'div[role="dialog"]', 'body']:
                 if not element_exists(page, container):
                     continue
                 
                 text = page.locator(container).first.inner_text(timeout=500).lower()
                 for indicator in CAPTCHA_INDICATORS:
                     if indicator in text:
                         # Double check string length to avoid matching long paragraphs
                         if len(text) < 500: 
                             return f"text_match:{indicator}"
        except Exception:
             pass

    except Exception as exc:
        logger.debug("detect_challenge error: %s", exc)

    return None


def handle_challenge(page, phase: str | None = None, capture_debug: bool | None = None) -> bool:
    """If a challenge is detected, try to dismiss it, then back off.

    phase: Optional label (feed, hashtag, profile, suggested, upload) for logs and debug capture.
    capture_debug: If True, save screenshot + HTML to debug/ when challenge is detected.
    Returns True if a challenge was found, False if page is clean.
    """
    # ── DIAGNOSTIC: Log page state before challenge detection ──
    try:
        url = page.url
        diag_state = page.evaluate("""() => {
            const hasDialog = document.querySelector('div[role="dialog"]') !== null;
            const hasSecsdk = document.querySelector('[class*="secsdk"]') !== null;
            const hasCaptcha = document.querySelector('[class*="captcha"]') !== null;
            const hasVerify = document.querySelector('[class*="Verify"]') !== null;
            const bodyText = (document.body?.innerText || "").toLowerCase();
            const hasSliderText = bodyText.includes("slider") || bodyText.includes("puzzle") || bodyText.includes("drag");
            return { hasDialog, hasSecsdk, hasCaptcha, hasVerify, hasSliderText, url: window.location.href };
        }""")
        logger.warning(
            "[DIAGNOSTIC] Challenge check (phase=%s): url=%s, dialog=%s, secsdk=%s, captcha=%s, verify=%s, sliderText=%s",
            phase or "unknown", url, diag_state.get("hasDialog", False), diag_state.get("hasSecsdk", False),
            diag_state.get("hasCaptcha", False), diag_state.get("hasVerify", False), diag_state.get("hasSliderText", False)
        )
    except Exception as diag_err:
        logger.debug("[DIAGNOSTIC] Failed to get page state: %s", diag_err)
    
    challenge = detect_challenge(page, phase=phase)
    if challenge is None:
        _throttle.decay(0.2)
        return False

    logger.warning("[CHALLENGE DETECTED] %s (phase=%s)", challenge, phase or "unknown")
    if phase:
        logger.warning("CAPTCHA occurred during: %s", phase)

    # Optional: save screenshot + HTML for root-cause analysis
    if capture_debug is None:
        try:
            from config import DEBUG_CAPTCHA_CAPTURE, DEBUG_DIR
            capture_debug = DEBUG_CAPTCHA_CAPTURE
        except Exception:
            capture_debug = False
    if capture_debug:
        try:
            import os
            from config import DEBUG_DIR
            os.makedirs(DEBUG_DIR, exist_ok=True)
            debug_dir = DEBUG_DIR
            ts = int(time.time())
            page.screenshot(path=os.path.join(debug_dir, f"captcha_{ts}.png"), full_page=False)
            html = page.content()
            with open(os.path.join(debug_dir, f"captcha_{ts}.html"), "w", encoding="utf-8") as f:
                f.write(html)
            logger.warning("CAPTCHA debug saved: %s/captcha_%s.* (phase=%s)", debug_dir, ts, phase or "unknown")
        except Exception as e:
            logger.debug("Could not save CAPTCHA debug: %s", e)

    _throttle.bump(2.5, reason=challenge)

    if "captcha" in challenge.lower():
        _throttle.captcha_count += 1

    # ── Step 1: Try to SOLVE the CAPTCHA programmatically ──
    try:
        from captcha_solver import attempt_solve_captcha
        from config import DEBUG_DIR
        solved = attempt_solve_captcha(page, debug_dir=DEBUG_DIR)
        if solved:
            logger.info("[CHALLENGE] CAPTCHA solved programmatically! Resuming.")
            _throttle.decay(1.5)
            time.sleep(random.uniform(3, 8))
            return True
    except Exception as solve_err:
        logger.debug("[CHALLENGE] CAPTCHA solver error: %s", solve_err)

    # ── Step 2: Try to DISMISS the CAPTCHA by closing its dialog ──
    dismissed = _try_dismiss_captcha(page)
    if dismissed:
        logger.info("[CHALLENGE] CAPTCHA dialog dismissed. Short cooldown …")
        cooldown = random.uniform(10, 25)
        time.sleep(cooldown)
        # Check if it actually went away
        if detect_challenge(page) is None:
            logger.info("[CHALLENGE] CAPTCHA cleared after dismiss. Resuming.")
            _throttle.decay(1.0)  # partly recover suspicion
            return True  # was challenge, but resolved

    # ── Step 3: Dismiss failed — full backoff ──
    if _throttle.is_critical:
        pause_secs = random.uniform(180, 360)
        logger.warning(
            "[Throttle] CRITICAL suspicion (%.1f). "
            "Backing off for %.0f s …",
            _throttle.suspicion_score, pause_secs,
        )
    else:
        pause_secs = random.uniform(60, 180)
        logger.info(
            "[Throttle] Suspicion %.1f – backing off %.0f s …",
            _throttle.suspicion_score, pause_secs,
        )

    time.sleep(pause_secs)

    # Navigate to homepage to clear the CAPTCHA page
    try:
        page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=30000)
        time.sleep(random.uniform(5, 10))
    except Exception:
        pass

    return True


def _try_dismiss_captcha(page) -> bool:
    """Try to close a CAPTCHA dialog by clicking its X/close button.

    Returns True if a close button was found and clicked.
    """
    close_selectors = [
        # TikTok slider puzzle: X in top-right of "Drag the slider to fit the puzzle" modal
        'div[role="dialog"] button[aria-label="Close"]',
        'div[role="dialog"] button[aria-label="close"]',
        '[class*="secsdk"] button[aria-label="Close"]',
        '[class*="Verify"] button[aria-label="Close"]',
        '[class*="captcha"] button[aria-label="Close"]',
        '[class*="DivCloseWrapper"]',
        # Close / X buttons commonly used in CAPTCHA modals
        '[class*="captcha"] button[class*="close"]',
        '[class*="captcha"] [class*="Close"]',
        '[class*="Verify"] button[class*="close"]',
        '[class*="secsdk"] [class*="close"]',
        '[class*="captcha-modal"] button',
        'div[class*="captcha"] ~ button',
        'div[class*="captcha"] svg[class*="close"]',
        'button[aria-label="Close"]',
        'button[aria-label="close"]',
    ]

    for sel in close_selectors:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=800):
                btn.click(timeout=2000)
                logger.info("[CAPTCHA DISMISS] Clicked close via: %s", sel)
                time.sleep(random.uniform(2, 4))
                return True
        except Exception:
            continue

    # Fallback: try pressing Escape key
    try:
        page.keyboard.press("Escape")
        time.sleep(random.uniform(1, 2))
        logger.info("[CAPTCHA DISMISS] Pressed Escape key.")
        return True
    except Exception:
        pass

    return False


# ──────────────────────────────────────────────
# Viewport Randomisation
# ──────────────────────────────────────────────

COMMON_VIEWPORTS = [
    (1280, 720),
    (1280, 800),
    (1366, 768),
    (1440, 900),
    (1536, 864),
    (1600, 900),
    (1920, 1080),
]


def random_viewport() -> dict:
    """Return a slightly jittered viewport from common resolutions."""
    base_w, base_h = random.choice(COMMON_VIEWPORTS)
    return {
        "width": base_w + random.randint(-16, 16),
        "height": base_h + random.randint(-12, 12),
    }


# ──────────────────────────────────────────────
# Browser Fingerprint Hardening
# ──────────────────────────────────────────────

def get_fingerprint_scripts(user_agent: str) -> str:
    """Return a JS payload that hardens the browser fingerprint
    beyond what playwright-stealth covers.
    """
    hw_concurrency = random.choice([4, 6, 8, 12])
    dev_memory = random.choice([4, 8, 16])
    # Use a per-session seed for consistent canvas noise within a session
    canvas_seed = random.randint(1, 2**31)

    return """
    // --- webdriver (belt-and-suspenders with --disable-blink-features) ---
    Object.defineProperty(navigator, 'webdriver', {
        get: () => false,
        configurable: true
    });

    // --- plugins (mimic real Chrome – PluginArray-like) ---
    (function() {
        const pluginData = [
            { name: 'PDF Viewer', filename: 'internal-pdf-viewer',
              description: 'Portable Document Format',
              mimeTypes: [{ type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' }] },
            { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer',
              description: 'Portable Document Format',
              mimeTypes: [{ type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: '' }] },
            { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer',
              description: 'Portable Document Format',
              mimeTypes: [{ type: 'application/pdf', suffixes: 'pdf', description: '' }] },
        ];
        const plugins = Object.create(PluginArray.prototype);
        pluginData.forEach((p, i) => { plugins[i] = p; });
        Object.defineProperty(plugins, 'length', { get: () => pluginData.length });
        Object.defineProperty(navigator, 'plugins', {
            get: () => plugins,
            configurable: true
        });
    })();

    // --- languages ---
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
        configurable: true
    });

    // --- chrome runtime (realistic structure) ---
    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {
            OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
            OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
            PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
            PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
            PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
            RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' },
            connect: function() { return { onDisconnect: { addListener: function() {} }, onMessage: { addListener: function() {} }, postMessage: function() {} }; },
            sendMessage: function() {},
            id: undefined,
        };
    }
    // Make chrome.app realistic
    if (!window.chrome.app) {
        window.chrome.app = {
            isInstalled: false,
            InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
            RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
            getDetails: function() { return null; },
            getIsInstalled: function() { return false; },
        };
    }

    // --- permissions query ---
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => {
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: Notification.permission });
        }
        return originalQuery(parameters);
    };

    // --- connection (NetworkInformation) ---
    if (!navigator.connection) {
        Object.defineProperty(navigator, 'connection', {
            get: () => ({
                effectiveType: '4g',
                rtt: """ + str(random.choice([50, 75, 100])) + """,
                downlink: """ + str(random.choice([5, 8, 10, 15])) + """,
                saveData: false,
            }),
            configurable: true
        });
    }

    // --- hardware concurrency (realistic value, consistent per session) ---
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => """ + str(hw_concurrency) + """,
        configurable: true
    });

    // --- device memory ---
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => """ + str(dev_memory) + """,
        configurable: true
    });

    // --- canvas noise (seeded, realistic per-session fingerprint) ---
    (function() {
        const seed = """ + str(canvas_seed) + """;
        // Simple seeded PRNG for consistent noise within a session
        let s = seed;
        function nextRand() {
            s = (s * 1103515245 + 12345) & 0x7fffffff;
            return (s >> 16) & 0xff;
        }

        const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            if (this.width === 0 || this.height === 0) {
                return origToDataURL.apply(this, arguments);
            }
            try {
                const ctx = this.getContext('2d');
                if (ctx) {
                    // Apply subtle noise to a few scattered pixels (not just first 2)
                    const w = Math.min(this.width, 16);
                    const h = Math.min(this.height, 16);
                    const imgData = ctx.getImageData(0, 0, w, h);
                    const pixelCount = w * h;
                    // Modify ~10% of pixels with +-1 noise
                    for (let p = 0; p < pixelCount; p++) {
                        if (nextRand() % 10 === 0) {
                            const idx = p * 4;
                            const channel = nextRand() % 3; // R, G, or B
                            const delta = (nextRand() % 3) - 1; // -1, 0, or +1
                            imgData.data[idx + channel] = Math.max(0, Math.min(255, imgData.data[idx + channel] + delta));
                        }
                    }
                    ctx.putImageData(imgData, 0, 0);
                }
            } catch(e) {}
            return origToDataURL.apply(this, arguments);
        };

        // Also hook toBlob
        const origToBlob = HTMLCanvasElement.prototype.toBlob;
        HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {
            // Trigger our noise via toDataURL first
            try { this.toDataURL(type); } catch(e) {}
            return origToBlob.apply(this, arguments);
        };
    })();

    // --- WebGL renderer/vendor (platform-aware) ---
    (function() {
        const getParam = WebGLRenderingContext.prototype.getParameter;
        // Let real WebGL values pass through — overriding creates detectable mismatch
        // Only override if values are missing/empty (e.g. software renderer)
        WebGLRenderingContext.prototype.getParameter = function(param) {
            const val = getParam.apply(this, arguments);
            if (param === 37445 && (!val || val === '')) return 'Google Inc.';
            if (param === 37446 && (!val || val === '')) return 'ANGLE (Google, Vulkan 1.3.0, OpenGL ES 3.2)';
            return val;
        };
        // Same for WebGL2
        if (typeof WebGL2RenderingContext !== 'undefined') {
            const getParam2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = function(param) {
                const val = getParam2.apply(this, arguments);
                if (param === 37445 && (!val || val === '')) return 'Google Inc.';
                if (param === 37446 && (!val || val === '')) return 'ANGLE (Google, Vulkan 1.3.0, OpenGL ES 3.2)';
                return val;
            };
        }
    })();

    // --- track mouse position (non-enumerable, hidden from detection) ---
    Object.defineProperty(window, '__mPos', {
        value: { x: 0, y: 0 },
        writable: true,
        enumerable: false,
        configurable: false
    });
    document.addEventListener('mousemove', (e) => {
        window.__mPos.x = e.clientX;
        window.__mPos.y = e.clientY;
    }, { passive: true });
    """
