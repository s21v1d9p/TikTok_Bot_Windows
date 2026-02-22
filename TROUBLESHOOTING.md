# TikTok Browser Bot - Troubleshooting Guide

This guide covers common issues and their solutions when running the TikTok Browser Bot on Windows.

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Login Issues](#login-issues)
3. [CAPTCHA Issues](#captcha-issues)
4. [Performance Issues](#performance-issues)
5. [Unattended Mode Issues](#unattended-mode-issues)
6. [Error Messages Reference](#error-messages-reference)

---

## Installation Issues

### "Python is not recognized as an internal or external command"

**Cause**: Python is not in your system PATH.

**Solution**:
1. Reinstall Python
2. During installation, check **"Add Python to PATH"**
3. Or manually add Python to PATH:
   - Press `Win + R`, type `sysdm.cpl`
   - Go to **Advanced → Environment Variables**
   - Under "System variables", find "Path"
   - Add: `C:\Users\<YourUser>\AppData\Local\Programs\Python\Python3xx\`
   - Add: `C:\Users\<YourUser>\AppData\Local\Programs\Python\Python3xx\Scripts\`

### "pip install fails with permission error"

**Cause**: Insufficient permissions.

**Solution**:
```cmd
# Run CMD as Administrator, then:
pip install -r requirements.txt
```

### "playwright install chromium fails"

**Cause**: Network issues or antivirus blocking.

**Solution**:
1. Temporarily disable antivirus
2. Try with VPN if in a restricted region
3. Manual install:
   ```cmd
   playwright install chromium --with-deps
   ```

### "ModuleNotFoundError: No module named 'phantomwright'"

**Cause**: Virtual environment not activated or dependencies not installed.

**Solution**:
```cmd
# Activate virtual environment
venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt
```

---

## Login Issues

### "QR code not appearing"

**Cause**: Browser launch failure or network issues.

**Solution**:
1. Check your internet connection
2. Clear browser data:
   ```cmd
   rmdir /s /q browser_data
   rmdir /s /q chrome_profile
   ```
3. Try again with option [2] in the menu

### "Session expired" or "Please log in again"

**Cause**: TikTok session cookies expired.

**Solution**:
1. Run the bot
2. Select option **[2] Re-do manual login**
3. Scan the QR code again
4. New session will be saved

### "Login check negative, waiting 5s and retrying"

**Cause**: Slow page load or temporary network issues.

**Solution**:
This is normal behavior. The bot retries login detection. If it persists:
1. Check internet connection
2. Try a different network (VPN may help)
3. Clear browser data and re-login

### "auth.json file not found"

**Cause**: First-time run without login.

**Solution**:
1. Run `python main.py`
2. Select option **[2] Re-do manual login**
3. Complete QR code login
4. `auth.json` will be created automatically

---

## CAPTCHA Issues

### "CAPTCHA detected during profile visit"

**Cause**: TikTok detected automated behavior.

**What the bot does automatically**:
1. Attempts to solve the CAPTCHA programmatically
2. If unsuccessful, dismisses the dialog
3. Backs off with increasing delays
4. Logs the incident for analysis

**Manual intervention** (if needed):
1. The bot window should remain open
2. If CAPTCHA appears, you can manually solve it
3. The bot will continue after you complete it

**Prevention tips**:
- Reduce `MAX_FOLLOWS_PER_SESSION` in `config.py`
- Increase cooldown times
- Run fewer sessions per day

### "Slider CAPTCHA keeps appearing"

**Cause**: Session is flagged for suspicious activity.

**Solutions**:

1. **Wait it out**: Stop the bot for 24-48 hours
2. **New session**: Re-login with option [2]
3. **Reduce activity**: Lower these values in `config.py`:
   ```python
   MAX_FOLLOWS_PER_SESSION = 2  # Reduce from 8
   MAX_LIKES_PER_SESSION = 5    # Reduce from 20
   ```

### "CAPTCHA screenshots in debug folder"

These are saved automatically when CAPTCHA is detected. Use them to:
- Verify what type of CAPTCHA appeared
- Report issues if needed
- Delete old screenshots periodically to save disk space

### "Bot doesn't detect CAPTCHA"

**Cause**: CAPTCHA detection gap (fixed in latest version).

**Solution**:
Ensure you have the latest version with shadow DOM detection. Check `stealth.py` for the `_detect_captcha_in_shadow_dom` function.

---

## Performance Issues

### "Bot is running slow"

**Cause**: Intentional human-like delays to avoid detection.

**Normal delays**:
- Between videos: 5-45 seconds
- Between profile visits: 25-75 seconds
- Pre-hashtag pause: 35-75 seconds

**These are NOT bugs** - they're anti-detection features.

### "Video playback errors"

**Cause**: TikTok's player issues or network problems.

**What the bot does**: Automatically scrolls to next video.

**If frequent**:
1. Check internet speed
2. Try a different network
3. The bot will continue with available videos

### "Browser window is blank/white"

**Cause**: GPU acceleration issues.

**Solution**:
1. Close the bot
2. Edit `tiktok_bot.py` to add `--disable-gpu` flag (already included)
3. Or run with software rendering:
   ```cmd
   set QT_OPENGL=software
   python main.py
   ```

### "High CPU/Memory usage"

**Cause**: Browser automation is resource-intensive.

**Solutions**:
1. Close other applications
2. Reduce `MAX_VIDEOS_TO_WATCH` in `config.py`
3. Run fewer sessions per day

---

## Unattended Mode Issues

### "Bot stops when I lock my computer"

**Cause**: Windows suspends processes when locked.

**Solutions**:

1. **Don't lock the computer** - Use a screensaver instead
2. **Use a dedicated machine** or VM
3. **Disable sleep**:
   - Settings → System → Power & Sleep
   - Set all options to "Never"

### "Bot stops overnight"

**Cause**: Sleep schedule or Windows updates.

**Check**:
1. `config.py` has `SLEEP_START = 22` and `SLEEP_END = 7`
   - This is intentional - bot pauses from 10 PM to 7 AM
2. Windows Update may have restarted the computer

**Solution for Windows Update**:
- Settings → Update & Security → Windows Update
- Advanced Options → Pause updates

### "Task Scheduler doesn't run the bot"

**Cause**: Incorrect task configuration.

**Solution**:
1. Open Task Scheduler
2. Find your task → Properties
3. Check:
   - **Run whether user is logged on or not**
   - **Run with highest privileges**
   - **Start in** folder is set correctly

### "Bot crashes silently"

**Cause**: Unhandled exception.

**Solution**:
1. Check `bot.log` for error messages
2. Look for Python tracebacks
3. Report the issue with log excerpt

---

## Error Messages Reference

### Browser Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Target page, context or browser has been closed` | Browser crashed | Restart bot, check for Chrome updates |
| `net::ERR_CONNECTION_REFUSED` | Network issue | Check internet, try VPN |
| `net::ERR_SSL_PROTOCOL_ERROR` | SSL/TLS issue | Update certificates, check antivirus |
| `Timeout 30000ms exceeded` | Page load timeout | Check internet speed, retry |

### Authentication Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `No active session in Chrome profile` | Normal - first run | Bot will load from `auth.json` |
| `Auto-login failed` | Expired session | Re-login with option [2] |
| `Session is not valid` | Cookies expired | Re-login with option [2] |

### CAPTCHA Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `captcha_element:[class*="secsdk"]` | Slider CAPTCHA detected | Bot handles automatically |
| `dialog_with_disabled_button` | CAPTCHA dialog detected | Bot handles automatically |
| `shadow_dom:#captcha_slide_button` | CAPTCHA in shadow DOM | Bot handles automatically |

### Rate Limiting

| Error | Cause | Solution |
|-------|-------|----------|
| `Soft-block suspected` | TikTok rate limiting | Wait 24-48 hours |
| `Throttle critical` | Multiple CAPTCHAs | Reduce activity, wait |
| `Too many requests` | Rate limited | Wait, reduce frequency |

---

## Diagnostic Tools

### Check Bot Logs

```cmd
type bot.log | more
```

Or open `bot.log` in any text editor.

### Check CAPTCHA Screenshots

Navigate to `debug/` folder to view captured CAPTCHA images.

### Verify Configuration

```cmd
type config.py | findstr "MAX_"
```

Shows current safety limits.

### Test Browser Launch

```cmd
venv\Scripts\activate
python -c "from phantomwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(); print('OK'); b.close(); p.stop()"
```

Should print "OK" if browser works.

---

## Getting Help

If issues persist:

1. **Collect diagnostic information**:
   - `bot.log` (last 100 lines)
   - Any CAPTCHA screenshots from `debug/`
   - Your `config.py` (remove sensitive info)

2. **Check for updates**:
   - New versions may fix known issues

3. **Test with minimal config**:
   ```python
   MAX_FOLLOWS_PER_SESSION = 1
   MAX_LIKES_PER_SESSION = 1
   MAX_VIDEOS_TO_WATCH = 3
   ```
   If this works, gradually increase values.

---

## Prevention Best Practices

1. **Don't run 24/7** - Use the sleep schedule feature
2. **Start slow** - Begin with low limits, increase gradually
3. **Monitor logs** - Check `bot.log` daily for issues
4. **Use a dedicated account** - Don't use your personal TikTok
5. **Respect rate limits** - If CAPTCHA appears, wait before retrying
6. **Keep session fresh** - Re-login weekly to prevent session expiry
