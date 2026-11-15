
import sqlite3
from getpass import getpass
from werkzeug.security import generate_password_hash

from database import get_db_connection


def create_admin():
    connection = None

    try:
        connection = get_db_connection()

        print("=== KYC MONITOR ADMIN SETUP ===")

        username = input("Enter admin username: ").strip()

        if not username:
            print("Username cannot be empty.")
            return

        existing = connection.execute(
            "SELECT admin_id FROM admins WHERE username = ?",
            (username,)
        ).fetchone()

        if existing:
            print("This username already exists.")
            return

        password = getpass("Enter new password: ")
        confirm = getpass("Confirm password: ")

        if len(password) < 12:
            print("Password must be at least 12 characters.")
            return

        if password != confirm:
            print("Passwords do not match.")
            return

        hashed_password = generate_password_hash(password)

        connection.execute(
            """
            INSERT INTO admins (username, password)
            VALUES (?, ?)
            """,
            (username, hashed_password)
        )

        connection.commit()

        print("\nAdmin account created successfully!")
        print("Username:", username)
        print("Password stored securely as a hash.")

    except (sqlite3.Error, ValueError) as error:
        if connection:
            connection.rollback()
        print("Admin creation failed:", error)

    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    create_admin()
