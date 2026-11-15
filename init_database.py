
import sqlite3
from database import get_db_connection, DATABASE_PATH


def initialize_database():
    connection = None

    try:
        connection = get_db_connection()

        connection.executescript("""
            -- 1. ADMIN TABLE
            CREATE TABLE IF NOT EXISTS admins (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            );

            -- 2. BRANCHES TABLE
            CREATE TABLE IF NOT EXISTS branches (
                branch_id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_code TEXT NOT NULL UNIQUE,
                branch_name TEXT NOT NULL,
                city TEXT NOT NULL
            );

            -- 3. CUSTOMERS TABLE
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_number TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                dob TEXT,
                phone TEXT,
                email TEXT,
                branch_id INTEGER,
                account_type TEXT,
                account_number TEXT,
                kyc_document TEXT,
                kyc_issue_date TEXT,
                kyc_expiry_date TEXT,
                kyc_status TEXT DEFAULT 'Pending',

                FOREIGN KEY (branch_id)
                    REFERENCES branches(branch_id)
            );

            -- 4. JOINT ACCOUNT HOLDERS TABLE
            CREATE TABLE IF NOT EXISTS joint_account_holders (
                holder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_number TEXT NOT NULL,
                holder_name TEXT NOT NULL,
                dob TEXT,
                phone TEXT,
                email TEXT,
                kyc_document TEXT,
                kyc_issue_date TEXT,
                kyc_expiry_date TEXT,
                kyc_status TEXT DEFAULT 'Pending'
            );

            -- 5. RE-KYC SCHEDULE TABLE
            CREATE TABLE IF NOT EXISTS rekyc_schedule (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                scheduled_date TEXT NOT NULL,
                status TEXT DEFAULT 'Pending',
                remarks TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (customer_id)
                    REFERENCES customers(customer_id)
            );


        CREATE TABLE IF NOT EXISTS joint_rekyc_schedule (
            schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
            holder_id INTEGER NOT NULL,
            scheduled_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            remarks TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (holder_id) REFERENCES joint_account_holders(holder_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_joint_rekyc_holder ON joint_rekyc_schedule(holder_id);

            -- SHORT-LIVED RECOVERY CODES (hashed, not plaintext)
            CREATE TABLE IF NOT EXISTS admin_password_resets (
                token_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at INTEGER NOT NULL,
                used_at INTEGER,
                FOREIGN KEY (admin_id) REFERENCES admins(admin_id) ON DELETE CASCADE
            );

            -- INDEXES FOR FASTER SEARCH
            CREATE INDEX IF NOT EXISTS idx_customers_branch
                ON customers(branch_id);

            CREATE INDEX IF NOT EXISTS idx_customers_expiry
                ON customers(kyc_expiry_date);

            CREATE INDEX IF NOT EXISTS idx_rekyc_customer
                ON rekyc_schedule(customer_id);

            CREATE INDEX IF NOT EXISTS idx_joint_account
                ON joint_account_holders(account_number);
        """)

        connection.commit()

        print("SQLite database initialized successfully!")
        print("Database location:", DATABASE_PATH)

        cursor = connection.execute("""
            SELECT name FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)

        print("\nAvailable tables:")

        for table in cursor.fetchall():
            print("-", table["name"])

    except sqlite3.Error as error:
        print("Database initialization failed:", error)

    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    initialize_database()
