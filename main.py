"""
main.py – Entry point for the TikTok Browser Bot.

Usage:
    python main.py

On first run the user is prompted to log in manually (QR code).
On subsequent runs the saved session is loaded and the bot enters its
scheduled automation loop.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime

import schedule

from bot_utils import logger, random_sleep, wait_until_active
from config import COOKIES_PATH, DELAY_LONG, SCHEDULE_FILE
from tiktok_bot import TikTokBot

# ──────────────────────────────────────────────
# Scheduled Job
# ──────────────────────────────────────────────

bot: TikTokBot | None = None


def scheduled_session() -> None:
    """Wrapper executed by the scheduler."""
    global bot
    if bot is None:
        return
    try:
        wait_until_active()
        bot.run_session()
    except Exception as exc:
        logger.error("Scheduled session error: %s\n%s", exc, traceback.format_exc())


# ──────────────────────────────────────────────
# Video Scheduling Helpers
# ──────────────────────────────────────────────

def add_scheduled_video() -> None:
    """Interactive prompt to schedule a video for later upload."""
    video_path = input("Enter the full path to the video file: ").strip().strip('"').strip("'")
    if not os.path.isfile(video_path):
        print(f"\n  Error: File not found: {video_path}")
        return

    caption = input("Enter the caption: ").strip()

    print("\nWhen should this video be posted?")
    print("  Format: YYYY-MM-DD HH:MM  (24-hour time, local timezone)")
    print("  Example: 2026-02-13 14:30")
    time_str = input("Scheduled time: ").strip()

    try:
        scheduled_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        if scheduled_time <= datetime.now():
            print("\n  Warning: That time is in the past. The video will be uploaded on next session.")
    except ValueError:
        print("\n  Error: Invalid date format. Use YYYY-MM-DD HH:MM")
        return

    # Load existing schedule
    schedules = []
    if os.path.isfile(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r", encoding="utf-8") as fh:
                schedules = json.load(fh)
        except (json.JSONDecodeError, IOError):
            schedules = []

    # Add new entry
    entry = {
        "video_path": os.path.abspath(video_path),
        "caption": caption,
        "scheduled_time": scheduled_time.isoformat(),
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    schedules.append(entry)

    with open(SCHEDULE_FILE, "w", encoding="utf-8") as fh:
        json.dump(schedules, fh, indent=2)

    print(f"\n  ✓ Video scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"    File: {video_path}")
    print(f"    Caption: {caption[:60]}{'…' if len(caption) > 60 else ''}")


def view_scheduled_videos() -> None:
    """Display all scheduled videos and their status."""
    if not os.path.isfile(SCHEDULE_FILE):
        print("\n  No videos scheduled.")
        return

    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as fh:
            schedules = json.load(fh)
    except (json.JSONDecodeError, IOError):
        print("\n  No videos scheduled.")
        return

    if not schedules:
        print("\n  No videos scheduled.")
        return

    print(f"\n  {'#':<3} {'Status':<10} {'Scheduled Time':<20} {'Caption':<40} {'File'}")
    print("  " + "─" * 100)
    for i, entry in enumerate(schedules, 1):
        status = entry.get("status", "pending")
        sched = entry.get("scheduled_time", "N/A")[:16]
        caption = entry.get("caption", "")[:38]
        video = os.path.basename(entry.get("video_path", "N/A"))
        status_icon = {"pending": "⏳", "done": "✓", "failed": "✗"}.get(status, "?")
        print(f"  {i:<3} {status_icon} {status:<8} {sched:<20} {caption:<40} {video}")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    global bot

    print("\n" + "=" * 50)
    print("   TikTok Browser Bot – Trading Niche")
    print("=" * 50)

    first_run = not os.path.isfile(COOKIES_PATH)

    if not first_run:
        choice = input(
            "\nSaved session found. What would you like to do?\n"
            "  [1] Start automation (auto-login + scheduled loop)\n"
            "  [2] Re-do manual login (overwrite session)\n"
            "  [3] Upload a video now\n"
            "  [4] Schedule a video for later\n"
            "  [5] View scheduled videos\n"
            "  [6] Exit\n"
            "Choice (1-6): "
        ).strip()
    else:
        print("\nNo saved session detected – starting first-run login.")
        choice = "2"

    # ── Manual Login ──
    if choice == "2":
        bot = TikTokBot()
        try:
            bot.login_manual()
        except Exception as exc:
            logger.error("Manual login failed: %s", exc)
        finally:
            bot.close()
            bot = None

        print("\nLogin complete. Please re-run the bot to start automation.")
        return

    # ── Video Upload (immediate) ──
    if choice == "3":
        video_path = input("Enter the full path to the video file: ").strip().strip('"').strip("'")
        caption = input("Enter the caption: ").strip()

        bot = TikTokBot()
        try:
            if not bot.login_auto():
                return
            random_sleep(*DELAY_LONG)
            success = bot.upload_content(video_path, caption)
            if success:
                print("\n  ✓ Video uploaded successfully.")
            else:
                print("\n  ✗ Video upload may have failed – check the log for details.")
        except Exception as exc:
            logger.error("Upload error: %s", exc)
        finally:
            if bot:
                bot.close()
                bot = None
        return

    # ── Schedule a Video ──
    if choice == "4":
        add_scheduled_video()
        return

    # ── View Scheduled Videos ──
    if choice == "5":
        view_scheduled_videos()
        return

    # ── Exit ──
    if choice == "6":
        print("Goodbye.")
        return

    # ── Auto Login + Scheduled Loop ──
    bot = TikTokBot()
    try:
        if not bot.login_auto():
            print(
                "\nAuto-login failed. Please re-run with manual login "
                "to refresh your session."
            )
            return

        logger.info("Starting scheduled automation loop …")
        print(
            "\nBot is now running. It will perform a session every ~2 hours.\n"
            "Press Ctrl+C to stop.\n"
        )

        # Run the first session immediately
        scheduled_session()

        # Schedule subsequent sessions every 2 hours (± jitter added inside)
        schedule.every(110).to(140).minutes.do(scheduled_session)

        while True:
            schedule.run_pending()
            time.sleep(30)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
        print("\nBot stopped.")
    except Exception as exc:
        logger.error("Fatal error: %s\n%s", exc, traceback.format_exc())
    finally:
        if bot:
            bot.close()
            bot = None


if __name__ == "__main__":
    main()
