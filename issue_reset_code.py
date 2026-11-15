"""Run locally on the database host to issue a single-use 15-minute recovery code.

For a hosted/production website, use email-based recovery with verified email
addresses instead. This utility is intended for a locally operated college demo.
"""
import hashlib
import secrets
import sqlite3
import time
from database import get_db_connection


def main():
    connection = None
    try:
        connection = get_db_connection()
        connection.execute("""CREATE TABLE IF NOT EXISTS admin_password_resets (
            token_id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at INTEGER NOT NULL,
            used_at INTEGER,
            FOREIGN KEY (admin_id) REFERENCES admins(admin_id) ON DELETE CASCADE
        )""")
        username = input("Admin username: ").strip()
        admin = connection.execute(
            "SELECT admin_id FROM admins WHERE username = ?", (username,)
        ).fetchone()
        if admin is None:
            print("Admin account not found. No code issued.")
            return
        token = secrets.token_urlsafe(24)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        connection.execute("DELETE FROM admin_password_resets WHERE admin_id = ?", (admin["admin_id"],))
        connection.execute(
            "INSERT INTO admin_password_resets (admin_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (admin["admin_id"], digest, int(time.time()) + 15 * 60)
        )
        connection.commit()
        print("\nOne-time recovery code (expires in 15 minutes):")
        print(token)
        print("Open /forgot-password on your locally running website.")
        print("Keep this code private. It cannot be viewed again.")
    except (sqlite3.Error, ValueError) as error:
        if connection is not None:
            connection.rollback()
        print("Unable to issue reset code:", error)
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()
