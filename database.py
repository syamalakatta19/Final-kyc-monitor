
import sqlite3
from datetime import date

# Explicit ISO date adapter (Python 3.12+ compatible).
sqlite3.register_adapter(date, lambda value: value.isoformat())
from pathlib import Path

# Main project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# SQLite database location
DATABASE_PATH = BASE_DIR / "kyc_monitor.db"


def get_db_connection():
    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=10
    )

    # Allows accessing columns by their names
    connection.row_factory = sqlite3.Row

    # Enable foreign key constraints
    connection.execute("PRAGMA foreign_keys = ON")

    return connection
