
import getpass
from werkzeug.security import generate_password_hash
from database import get_db_connection


def secure_admin_password():

    print("KYC Monitor - Secure Admin Password")
    print("-----------------------------------")

    username = input("Existing admin username: ").strip()
    if not username:
        print("Username is required.")
        return

    password = getpass.getpass("Enter your new admin password: ")
    confirm_password = getpass.getpass("Confirm your new password: ")

    if password != confirm_password:
        print("Error: Passwords do not match.")
        return

    if len(password) < 12:
        print("Error: Password must contain at least 12 characters.")
        return

    # Convert password into a secure hash
    password_hash = generate_password_hash(password)

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE admins
            SET password = ?
            WHERE username = ?
            """,
            (password_hash, username)
        )

        if cursor.rowcount == 1:
            connection.commit()
            print("Admin password updated successfully!")
            print("Password is now securely hashed.")
        else:
            connection.rollback()
            print("Admin account was not found. No changes made.")

    except Exception as error:
        if connection:
            connection.rollback()
        print("Database error:", error)

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


if __name__ == "__main__":
    secure_admin_password()
