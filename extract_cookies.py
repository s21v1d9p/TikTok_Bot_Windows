"""
extract_cookies.py – Extract TikTok cookies from Chrome's SQLite DB on macOS.

Works even while Chrome is running (copies the DB first).
Decrypts Chrome's encrypted cookie values using macOS Keychain.

Usage:  python3 extract_cookies.py
"""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

AUTH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth.json")

# Chrome cookie DB locations (macOS) — try all profiles
CHROME_BASE = os.path.expanduser("~/Library/Application Support/Google/Chrome")
POSSIBLE_PROFILES = ["Default", "Profile 1", "Profile 2", "Profile 3", "Default/Default"]


def get_chrome_encryption_key() -> bytes:
    """Get Chrome's cookie encryption key from macOS Keychain."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Chrome Safe Storage", "-w"],
            capture_output=True, text=True, check=True,
        )
        password = result.stdout.strip()
        import hashlib
        # Chrome on macOS uses PBKDF2-HMAC-SHA1 with 1003 iterations
        key = hashlib.pbkdf2_hmac("sha1", password.encode(), b"saltysalt", 1003, dklen=16)
        return key
    except subprocess.CalledProcessError:
        print("ERROR: Could not get Chrome encryption key from Keychain.")
        print("       You may need to allow access when the system prompt appears.")
        sys.exit(1)


def decrypt_value(encrypted_value: bytes, key: bytes) -> str:
    """Decrypt a Chrome-encrypted cookie value."""
    if not encrypted_value:
        return ""

    # v10 = AES-128-CBC with 3-byte prefix 'v10'
    if encrypted_value[:3] == b"v10":
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend

            iv = b" " * 16  # Chrome uses 16 spaces as IV
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(encrypted_value[3:]) + decryptor.finalize()
            # Remove PKCS7 padding
            padding_len = decrypted[-1]
            if isinstance(padding_len, int) and 1 <= padding_len <= 16:
                decrypted = decrypted[:-padding_len]
            return decrypted.decode("utf-8", errors="replace")
        except ImportError:
            print("ERROR: Need 'cryptography' package. Installing...")
            subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "cryptography"],
                           capture_output=True)
            # Retry after install
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            iv = b" " * 16
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(encrypted_value[3:]) + decryptor.finalize()
            padding_len = decrypted[-1]
            if isinstance(padding_len, int) and 1 <= padding_len <= 16:
                decrypted = decrypted[:-padding_len]
            return decrypted.decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  Decrypt error: {e}")
            return ""

    # Unencrypted (shouldn't happen on macOS but handle it)
    try:
        return encrypted_value.decode("utf-8", errors="replace")
    except Exception:
        return ""


def find_cookie_db() -> str | None:
    """Find Chrome's Cookies SQLite database."""
    for profile in POSSIBLE_PROFILES:
        path = os.path.join(CHROME_BASE, profile, "Cookies")
        if os.path.isfile(path):
            return path
    return None


def extract_tiktok_cookies(db_path: str, key: bytes) -> list[dict]:
    """Extract and decrypt TikTok cookies from Chrome's SQLite DB."""
    # Copy DB to temp (avoids lock issues while Chrome is running)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    shutil.copy2(db_path, tmp_path)

    # Also copy WAL and SHM if they exist (for consistency)
    for ext in ["-wal", "-shm"]:
        src = db_path + ext
        if os.path.isfile(src):
            shutil.copy2(src, tmp_path + ext)

    cookies = []
    try:
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # Query TikTok cookies
        cursor.execute("""
            SELECT host_key, name, encrypted_value, path, expires_utc,
                   is_secure, is_httponly, samesite
            FROM cookies
            WHERE host_key LIKE '%tiktok%'
            ORDER BY name
        """)

        SAME_SITE_MAP = {0: "None", 1: "Lax", 2: "Strict", -1: "None"}

        for row in cursor.fetchall():
            host, name, enc_val, path, expires_utc, secure, httponly, samesite = row

            value = decrypt_value(enc_val, key)
            if not value or not name:
                continue

            # Convert Chrome's expires_utc (microseconds since 1601-01-01) to Unix epoch
            if expires_utc and expires_utc > 0:
                # Chrome epoch: Jan 1, 1601. Unix epoch: Jan 1, 1970.
                # Difference: 11644473600 seconds
                expires = (expires_utc / 1_000_000) - 11644473600
            else:
                expires = -1  # Session cookie

            cookie = {
                "name": name,
                "value": value,
                "domain": host,
                "path": path or "/",
                "expires": expires,
                "httpOnly": bool(httponly),
                "secure": bool(secure),
                "sameSite": SAME_SITE_MAP.get(samesite, "Lax"),
            }
            cookies.append(cookie)

        conn.close()
    finally:
        # Clean up temp files
        for ext in ["", "-wal", "-shm"]:
            try:
                os.unlink(tmp_path + ext)
            except OSError:
                pass

    return cookies


def main():
    print("=" * 50)
    print("  TikTok Cookie Extractor (Chrome → auth.json)")
    print("=" * 50)
    print()

    db_path = find_cookie_db()
    if not db_path:
        print(f"ERROR: Chrome cookie database not found in any profile under:")
        print(f"       {CHROME_BASE}")
        sys.exit(1)

    print(f"Found cookie DB: {db_path}")
    print("Getting Chrome encryption key from Keychain...")
    print("  (You may see a macOS prompt — click 'Allow')")
    print()

    key = get_chrome_encryption_key()
    print("Encryption key obtained. Extracting TikTok cookies...")

    cookies = extract_tiktok_cookies(db_path, key)
    print(f"Found {len(cookies)} TikTok cookies.")

    if not cookies:
        print("ERROR: No TikTok cookies found. Are you logged in to TikTok in Chrome?")
        sys.exit(1)

    # Show key cookie status
    key_names = {"sessionid", "sid_tt", "uid_tt", "sid_guard", "sessionid_ss"}
    found = {c["name"] for c in cookies} & key_names
    missing = key_names - found

    print()
    if found:
        print(f"  ✓ Auth tokens found: {', '.join(sorted(found))}")
    if missing:
        print(f"  ⚠ Missing tokens: {', '.join(sorted(missing))}")

    # Save
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2)

    print(f"\n  ✓ Saved to: {AUTH_FILE}")
    print(f"    Total cookies: {len(cookies)}")
    print("\nDone! Run the bot with Option [1] to test.")


if __name__ == "__main__":
    main()
