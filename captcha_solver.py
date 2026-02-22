"""
captcha_solver.py – Practical CAPTCHA solver for TikTok's ByteDance secsdk puzzles.

Handles two CAPTCHA types:
1. Rotation puzzle: "Drag the slider to fit the puzzle" – rotate a circular image
2. Jigsaw slider: "Drag the puzzle piece into place" – slide piece to gap

Strategy:
- Screenshot the CAPTCHA area
- Use image analysis (Pillow) to determine correct position
- Drag the slider with human-like Bézier mouse movement
- Verify CAPTCHA cleared; retry with adjusted position if not
"""

from __future__ import annotations

import logging
import math
import os
import random
import time

logger = logging.getLogger("TikTokBot")

# Try importing Pillow (optional – solver degrades to incremental drag without it)
try:
    from PIL import Image, ImageFilter, ImageStat
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    logger.debug("Pillow not installed – CAPTCHA solver will use incremental strategy only.")


# ──────────────────────────────────────────────
# Rotation CAPTCHA Solver
# ──────────────────────────────────────────────

def _estimate_rotation_angle(image_path: str) -> float | None:
    """Estimate how many degrees a circular image needs to be rotated
    to reach its correct (upright) orientation.

    Heuristic: Analyze the image's edge distribution. Natural images
    tend to have strong horizontal edges at the bottom (ground/horizon)
    and lighter content at the top (sky). We rotate the image in 10°
    increments and find the orientation where the bottom half has more
    edge density than the top (indicating correct "ground down" position).

    Returns angle in degrees (0-360), or None if analysis fails.
    """
    if not HAS_PILLOW:
        return None

    try:
        img = Image.open(image_path).convert("L")  # grayscale

        # Crop to center circle (remove corners which are usually masked)
        w, h = img.size
        center_x, center_y = w // 2, h // 2
        radius = min(w, h) // 2 - 5

        best_angle = 0
        best_score = -999

        # Test every 15° rotation
        for angle in range(0, 360, 15):
            rotated = img.rotate(-angle, resample=Image.BICUBIC, fillcolor=128)

            # Edge detection
            edges = rotated.filter(ImageFilter.FIND_EDGES)

            # Score: bottom-half edge intensity minus top-half
            # Correct orientation has ground/detail at bottom
            top_half = edges.crop((0, 0, w, h // 2))
            bottom_half = edges.crop((0, h // 2, w, h))

            top_mean = ImageStat.Stat(top_half).mean[0]
            bottom_mean = ImageStat.Stat(bottom_half).mean[0]

            # Also check left-right symmetry (correct images tend to be more symmetric)
            left_half = edges.crop((0, 0, w // 2, h))
            right_half = edges.crop((w // 2, 0, w, h))
            lr_diff = abs(ImageStat.Stat(left_half).mean[0] - ImageStat.Stat(right_half).mean[0])

            # Score: prefer bottom-heavy edge distribution with symmetric sides
            score = (bottom_mean - top_mean) - lr_diff * 0.3

            if score > best_score:
                best_score = score
                best_angle = angle

        logger.info("Rotation analysis: best angle = %d° (score=%.1f)", best_angle, best_score)
        return float(best_angle)

    except Exception as e:
        logger.debug("Rotation analysis failed: %s", e)
        return None


def _find_slider_track(page) -> dict | None:
    """Find the slider track element and return its bounding box.

    TikTok's CAPTCHA slider is typically inside a secsdk container.
    """
    slider_selectors = [
        # Slider track (the bar you drag along)
        '[class*="secsdk"] [class*="slider"]',
        '[class*="captcha"] [class*="slider"]',
        '[class*="Verify"] [class*="slider"]',
        # The draggable handle
        '[class*="secsdk"] [class*="drag"]',
        '[class*="captcha"] [class*="drag"]',
        # Generic slider patterns
        '[class*="SliderContainer"] [class*="slider"]',
        '[class*="slider-bar"]',
        '[class*="slide_bar"]',
    ]

    for sel in slider_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=800):
                box = el.bounding_box(timeout=1000)
                if box and box["width"] > 20:
                    logger.debug("Found slider via: %s (box=%s)", sel, box)
                    return box
        except Exception:
            continue

    # Fallback: find via JS – look for narrow horizontal elements inside captcha
    try:
        box = page.evaluate("""() => {
            const containers = document.querySelectorAll(
                '[class*="secsdk"], [class*="captcha"], [class*="Verify"], div[role="dialog"]'
            );
            for (const c of containers) {
                // Find elements that look like slider tracks
                const candidates = c.querySelectorAll('div, span');
                for (const el of candidates) {
                    const r = el.getBoundingClientRect();
                    // Slider track: wide and narrow
                    if (r.width > 150 && r.height > 15 && r.height < 80 && r.width / r.height > 3) {
                        // Check if it has a draggable child
                        const child = el.querySelector('[class*="drag"], [class*="btn"], [class*="handle"]');
                        if (child || el.style.cursor === 'pointer') {
                            return { x: r.x, y: r.y, width: r.width, height: r.height };
                        }
                    }
                }
            }
            return null;
        }""")
        if box:
            logger.debug("Found slider via JS fallback: %s", box)
            return box
    except Exception:
        pass

    return None


def _find_captcha_image(page) -> dict | None:
    """Find the CAPTCHA puzzle image and return its bounding box."""
    image_selectors = [
        '[class*="secsdk"] img',
        '[class*="captcha"] img',
        '[class*="Verify"] img',
        'div[role="dialog"] img[src*="captcha"]',
        'div[role="dialog"] img[class*="puzzle"]',
        'div[role="dialog"] canvas',
    ]

    for sel in image_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=800):
                box = el.bounding_box(timeout=1000)
                if box and box["width"] > 50 and box["height"] > 50:
                    logger.debug("Found CAPTCHA image via: %s", sel)
                    return box
        except Exception:
            continue

    return None


def _human_drag_slider(page, slider_box: dict, fraction: float) -> None:
    """Drag the slider to a position expressed as fraction (0.0–1.0) of the track.

    Uses Bézier-like movement with variable speed to mimic a human drag.
    """
    # Start position: left edge of slider + small offset (the handle)
    start_x = slider_box["x"] + 15
    start_y = slider_box["y"] + slider_box["height"] / 2

    # End position: fraction along the track
    travel = (slider_box["width"] - 30) * fraction
    end_x = start_x + travel
    end_y = start_y + random.uniform(-2, 2)  # slight vertical wobble

    # Move to start
    page.mouse.move(start_x, start_y)
    time.sleep(random.uniform(0.1, 0.3))

    # Press and hold
    page.mouse.down()
    time.sleep(random.uniform(0.05, 0.15))

    # Generate drag path with acceleration and deceleration
    steps = random.randint(25, 45)
    for i in range(1, steps + 1):
        t = i / steps
        # Ease: fast start, slow at end (like a real drag)
        t_eased = 1 - (1 - t) ** 2.5

        curr_x = start_x + travel * t_eased
        # Add natural wobble (decreasing as we approach target)
        wobble_x = random.uniform(-1.5, 1.5) * (1 - t)
        wobble_y = random.uniform(-1.0, 1.0) * (1 - t * 0.5)

        page.mouse.move(
            curr_x + wobble_x,
            start_y + wobble_y,
        )
        # Variable speed: slower at start and end
        if t < 0.15 or t > 0.85:
            time.sleep(random.uniform(0.015, 0.035))
        else:
            time.sleep(random.uniform(0.005, 0.015))

    # Small overshoot and correction (human behavior)
    if random.random() < 0.4:
        overshoot = random.uniform(2, 6)
        page.mouse.move(end_x + overshoot, end_y)
        time.sleep(random.uniform(0.05, 0.12))
        page.mouse.move(end_x, end_y)
        time.sleep(random.uniform(0.05, 0.1))

    # Release
    time.sleep(random.uniform(0.08, 0.2))
    page.mouse.up()
    time.sleep(random.uniform(0.5, 1.0))


def solve_rotation_captcha(page, debug_dir: str | None = None) -> bool:
    """Attempt to solve a rotation-type CAPTCHA.

    Strategy:
    1. Screenshot the puzzle image for analysis
    2. Estimate correct rotation angle
    3. Drag slider to corresponding position
    4. Check if CAPTCHA cleared
    5. If not, try incremental adjustments

    Returns True if CAPTCHA appears solved, False otherwise.
    """
    logger.info("[CAPTCHA SOLVER] Attempting rotation puzzle solve …")

    slider_box = _find_slider_track(page)
    if not slider_box:
        logger.warning("[CAPTCHA SOLVER] Could not find slider track.")
        return False

    # Try to screenshot and analyze the puzzle image
    estimated_fraction = None
    if HAS_PILLOW and debug_dir:
        try:
            img_box = _find_captcha_image(page)
            if img_box:
                os.makedirs(debug_dir, exist_ok=True)
                img_path = os.path.join(debug_dir, "captcha_puzzle_temp.png")
                page.screenshot(
                    path=img_path,
                    clip={
                        "x": img_box["x"],
                        "y": img_box["y"],
                        "width": img_box["width"],
                        "height": img_box["height"],
                    },
                )
                angle = _estimate_rotation_angle(img_path)
                if angle is not None:
                    # Convert angle to slider fraction (0-360° → 0.0-1.0)
                    estimated_fraction = angle / 360.0
                    logger.info("[CAPTCHA SOLVER] Estimated rotation: %d° → fraction %.2f", angle, estimated_fraction)
        except Exception as e:
            logger.debug("[CAPTCHA SOLVER] Image analysis error: %s", e)

    # Attempt sequence: try estimated position first, then incremental adjustments
    attempts = []
    if estimated_fraction is not None:
        # Try estimated position first, then small adjustments around it
        attempts.append(estimated_fraction)
        for delta in [0.05, -0.05, 0.10, -0.10, 0.15, -0.15]:
            adj = (estimated_fraction + delta) % 1.0
            attempts.append(adj)
    else:
        # No image analysis – try common positions (incremental sweep)
        # Rotation CAPTCHAs often have the answer at multiples of ~30°
        attempts = [0.0, 0.25, 0.5, 0.75, 0.12, 0.37, 0.62, 0.87]

    for i, fraction in enumerate(attempts[:6]):  # max 6 attempts
        logger.info("[CAPTCHA SOLVER] Attempt %d/6: drag to %.0f%%", i + 1, fraction * 100)

        _human_drag_slider(page, slider_box, fraction)

        # Check if CAPTCHA cleared
        time.sleep(random.uniform(1.0, 2.0))

        from stealth import detect_challenge
        if detect_challenge(page) is None:
            logger.info("[CAPTCHA SOLVER] Rotation CAPTCHA solved on attempt %d!", i + 1)
            return True

        # Re-find slider (CAPTCHA may have reset)
        time.sleep(random.uniform(1.0, 2.0))
        slider_box = _find_slider_track(page)
        if not slider_box:
            logger.warning("[CAPTCHA SOLVER] Slider disappeared after attempt %d.", i + 1)
            return False

        # Small cooldown between retries
        time.sleep(random.uniform(1.5, 3.0))

    logger.warning("[CAPTCHA SOLVER] Rotation CAPTCHA not solved after %d attempts.", len(attempts[:6]))
    return False


# ──────────────────────────────────────────────
# Jigsaw Slider CAPTCHA Solver
# ──────────────────────────────────────────────

def _estimate_jigsaw_position(image_path: str) -> float | None:
    """Analyze a jigsaw CAPTCHA screenshot to find the gap position.

    The gap in a jigsaw CAPTCHA creates a distinct dark/light region
    that contrasts with the surrounding image. We look for a vertical
    strip of high contrast (the gap edge).

    Returns fraction (0.0–1.0) of where the gap is, or None.
    """
    if not HAS_PILLOW:
        return None

    try:
        img = Image.open(image_path).convert("L")
        w, h = img.size

        # Apply edge detection
        edges = img.filter(ImageFilter.FIND_EDGES)

        # Scan vertical strips looking for the one with highest edge density
        # The gap creates strong vertical edges
        strip_width = max(1, w // 40)
        best_x = w // 2
        best_score = 0

        # Skip the leftmost 15% (the puzzle piece starts there)
        start_x = int(w * 0.15)

        for x in range(start_x, w - strip_width, strip_width):
            strip = edges.crop((x, int(h * 0.2), x + strip_width, int(h * 0.8)))
            score = ImageStat.Stat(strip).mean[0]
            if score > best_score:
                best_score = score
                best_x = x

        fraction = best_x / w
        logger.info("Jigsaw analysis: gap at x=%d (%.0f%% of width, score=%.1f)", best_x, fraction * 100, best_score)
        return fraction

    except Exception as e:
        logger.debug("Jigsaw analysis failed: %s", e)
        return None


def solve_jigsaw_captcha(page, debug_dir: str | None = None) -> bool:
    """Attempt to solve a jigsaw/slider CAPTCHA.

    Strategy:
    1. Screenshot for gap detection
    2. Drag slider to estimated gap position
    3. Verify and retry with adjustments

    Returns True if solved, False otherwise.
    """
    logger.info("[CAPTCHA SOLVER] Attempting jigsaw puzzle solve …")

    slider_box = _find_slider_track(page)
    if not slider_box:
        logger.warning("[CAPTCHA SOLVER] Could not find slider track for jigsaw.")
        return False

    estimated_fraction = None
    if HAS_PILLOW and debug_dir:
        try:
            img_box = _find_captcha_image(page)
            if img_box:
                os.makedirs(debug_dir, exist_ok=True)
                img_path = os.path.join(debug_dir, "captcha_jigsaw_temp.png")
                page.screenshot(
                    path=img_path,
                    clip={
                        "x": img_box["x"],
                        "y": img_box["y"],
                        "width": img_box["width"],
                        "height": img_box["height"],
                    },
                )
                estimated_fraction = _estimate_jigsaw_position(img_path)
        except Exception as e:
            logger.debug("[CAPTCHA SOLVER] Jigsaw image analysis error: %s", e)

    # Attempt sequence
    attempts = []
    if estimated_fraction is not None:
        attempts.append(estimated_fraction)
        for delta in [0.03, -0.03, 0.06, -0.06, 0.10, -0.10]:
            adj = max(0.05, min(0.95, estimated_fraction + delta))
            attempts.append(adj)
    else:
        # Common gap positions (jigsaw gaps tend to be in the right ~60%)
        attempts = [0.45, 0.55, 0.65, 0.35, 0.75, 0.50]

    for i, fraction in enumerate(attempts[:5]):  # max 5 attempts
        logger.info("[CAPTCHA SOLVER] Jigsaw attempt %d/5: drag to %.0f%%", i + 1, fraction * 100)

        _human_drag_slider(page, slider_box, fraction)

        time.sleep(random.uniform(1.0, 2.0))

        from stealth import detect_challenge
        if detect_challenge(page) is None:
            logger.info("[CAPTCHA SOLVER] Jigsaw CAPTCHA solved on attempt %d!", i + 1)
            return True

        time.sleep(random.uniform(1.5, 3.0))
        slider_box = _find_slider_track(page)
        if not slider_box:
            logger.warning("[CAPTCHA SOLVER] Slider disappeared after jigsaw attempt %d.", i + 1)
            return False

    logger.warning("[CAPTCHA SOLVER] Jigsaw CAPTCHA not solved after attempts.")
    return False


# ──────────────────────────────────────────────
# Unified Solver Entry Point
# ──────────────────────────────────────────────

def attempt_solve_captcha(page, debug_dir: str | None = None) -> bool:
    """Main entry point: detect CAPTCHA type and attempt to solve it.

    Returns True if CAPTCHA was solved, False if not.
    """
    try:
        # Detect CAPTCHA type from page text
        page_text = ""
        try:
            page_text = page.inner_text("body", timeout=3000).lower()
        except Exception:
            pass

        if "fit the puzzle" in page_text or "rotate" in page_text:
            return solve_rotation_captcha(page, debug_dir)
        elif "drag the puzzle piece" in page_text or "slide" in page_text:
            return solve_jigsaw_captcha(page, debug_dir)
        else:
            # Try rotation first (most common on TikTok)
            logger.info("[CAPTCHA SOLVER] Unknown CAPTCHA type – trying rotation solver.")
            if solve_rotation_captcha(page, debug_dir):
                return True
            return solve_jigsaw_captcha(page, debug_dir)

    except Exception as e:
        logger.warning("[CAPTCHA SOLVER] Solver error: %s", e)
        return False
