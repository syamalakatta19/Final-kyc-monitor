
import os
import hashlib
import hmac
import secrets
import time
from pathlib import Path
from datetime import date, timedelta

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file
)

from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db_connection
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "frontend" / "templates"),
    static_folder=str(BASE_DIR / "frontend" / "static")
)

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_HTTPS", "false").lower() == "true"

if not app.config["SECRET_KEY"]:
    raise RuntimeError("FLASK_SECRET_KEY is missing from .env")



# --------------------------------------------------
# SQLITE RESULT ADAPTER
# --------------------------------------------------
# SQLite stores project dates as ISO text. This cursor preserves the mutable,
# dictionary-like rows and date objects expected by the existing Flask routes.
_SQLITE_DATE_COLUMNS = frozenset({
    "dob", "kyc_issue_date", "kyc_expiry_date", "scheduled_date"
})


def _sqlite_result(row):
    if row is None:
        return None
    result = dict(row)
    for field in _SQLITE_DATE_COLUMNS:
        value = result.get(field)
        if isinstance(value, str) and value:
            try:
                result[field] = parse_kyc_date(value)
            except ValueError:
                # Legacy text DOB formats remain untouched until normalized.
                pass
    return result


class SQLiteCursor:
    """Expose the row format used by the original Flask routes."""

    def __init__(self, connection):
        self._cursor = connection.cursor()

    def execute(self, sql, parameters=()):
        self._cursor.execute(sql, parameters)
        return self

    def fetchone(self):
        return _sqlite_result(self._cursor.fetchone())

    def fetchall(self):
        return [_sqlite_result(row) for row in self._cursor.fetchall()]

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()

# --------------------------------------------------
# KYC DATE NORMALIZATION & SHARED STATUS RULES
# --------------------------------------------------
DATE_INPUT_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y")


def parse_kyc_date(raw):
    """Accept ISO, day-month-year, and US month/day/year, store ISO dates."""
    if not raw:
        raise ValueError("A date is required")
    if isinstance(raw, date):
        return raw
    for fmt in DATE_INPUT_FORMATS:
        try:
            return __import__("datetime").datetime.strptime(str(raw).strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError("Date must use YYYY-MM-DD, DD-MM-YYYY or MM/DD/YYYY")


def kyc_status_for(expiry):
    if not expiry:
        return "Unknown"
    expiry = parse_kyc_date(expiry)
    if expiry < date.today():
        return "Expired"
    if expiry <= date.today() + timedelta(days=30):
        return "Expiring Soon"
    return "Valid"


def verify_joint_account(connection, account_number):
    """Require holders to reference an existing customer account."""
    return connection.execute(
        "SELECT 1 FROM customers WHERE account_number = ? LIMIT 1",
        (account_number,)
    ).fetchone() is not None


@app.context_processor
def inject_csrf_token():
    def csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_urlsafe(32)
        return session["_csrf_token"]
    return {"csrf_token": csrf_token}


@app.before_request
def ensure_joint_schedule_schema():
    # A small, additive migration for existing SQLite project databases.
    if not app.config.get("JOINT_REKYC_SCHEMA_READY", False):
        connection = get_db_connection()
        try:
            connection.execute("""CREATE TABLE IF NOT EXISTS joint_rekyc_schedule (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                holder_id INTEGER NOT NULL,
                scheduled_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                remarks TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(holder_id) REFERENCES joint_account_holders(holder_id) ON DELETE CASCADE
            )""")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_joint_rekyc_holder ON joint_rekyc_schedule(holder_id)")
            connection.commit()
        finally:
            connection.close()
        app.config["JOINT_REKYC_SCHEMA_READY"] = True


@app.before_request
def protect_state_changing_requests():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        expected = session.get("_csrf_token", "")
        supplied = request.form.get("_csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        if not expected or not supplied or not hmac.compare_digest(expected, supplied):
            return "Invalid or missing form security token. Reload the page and retry.", 400


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def home():
    if "admin_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# --------------------------------------------------
# ADMIN LOGIN
# --------------------------------------------------


# --------------------------------------------------


# --------------------------------------------------
# ADMIN LOGIN - SQLITE3
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if "admin_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        if not username or not password:
            flash(
                "Please enter your username and password.",
                "warning"
            )
            return render_template("login.html")

        connection = None

        try:
            # Connect to SQLite database
            connection = get_db_connection()

            # Get administrator details
            admin = connection.execute(
                """
                SELECT admin_id, username, password
                FROM admins
                WHERE username = ?
                """,
                (username,)
            ).fetchone()

            # Verify the hashed password
            if admin and check_password_hash(
                admin["password"], password
            ):

                session.clear()

                session["admin_id"] = admin["admin_id"]
                session["admin_username"] = admin["username"]

                flash(
                    "Login successful!",
                    "success"
                )

                return redirect(url_for("dashboard"))

            else:
                flash(
                    "Invalid username or password.",
                    "danger"
                )

        except Exception:
            app.logger.exception("Admin login failed")
            flash(
                "Unable to process login. Please try again.",
                "danger"
            )

        finally:
            if connection is not None:
                connection.close()

    return render_template("login.html")



# --------------------------------------------------
# FORGOT PASSWORD: ONE-TIME LOCAL RECOVERY CODE
# --------------------------------------------------

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    # The recovery code is issued separately on the local host by an
    # authorized operator through backend/issue_reset_code.py.
    if request.method == "GET":
        session["reset_csrf"] = secrets.token_urlsafe(32)
        return render_template("forgot_password.html", reset_form_token=session["reset_csrf"])

    submitted_csrf = request.form.get("csrf_token", "")
    expected_csrf = session.get("reset_csrf", "")
    if not expected_csrf or not hmac.compare_digest(expected_csrf, submitted_csrf):
        flash("The form expired. Please try again.", "danger")
        return redirect(url_for("forgot_password"))

    username = request.form.get("username", "").strip()
    recovery_code = request.form.get("recovery_code", "").strip()
    password = request.form.get("new_password", "")
    confirmation = request.form.get("confirm_password", "")

    if not username or not recovery_code or not password:
        flash("Please complete all fields.", "warning")
        return render_template("forgot_password.html", reset_form_token=expected_csrf)
    if len(password) < 12 or len(password) > 256:
        flash("Use a password between 12 and 256 characters.", "warning")
        return render_template("forgot_password.html", reset_form_token=expected_csrf)
    if password != confirmation:
        flash("New passwords do not match.", "warning")
        return render_template("forgot_password.html", reset_form_token=expected_csrf)

    connection = None
    try:
        connection = get_db_connection()
        connection.execute("BEGIN IMMEDIATE")
        admin = connection.execute(
            "SELECT admin_id FROM admins WHERE username = ?", (username,)
        ).fetchone()
        code_digest = hashlib.sha256(recovery_code.encode("utf-8")).hexdigest()
        reset_row = None
        if admin is not None:
            reset_row = connection.execute(
                """SELECT token_id FROM admin_password_resets
                   WHERE admin_id = ? AND token_hash = ?
                     AND used_at IS NULL AND expires_at > ?""",
                (admin["admin_id"], code_digest, int(time.time()))
            ).fetchone()

        if reset_row is None:
            connection.rollback()
            flash("Invalid or expired recovery code.", "danger")
            return render_template("forgot_password.html", reset_form_token=expected_csrf)

        connection.execute(
            "UPDATE admins SET password = ? WHERE admin_id = ?",
            (generate_password_hash(password), admin["admin_id"])
        )
        connection.execute(
            "DELETE FROM admin_password_resets WHERE admin_id = ?",
            (admin["admin_id"],)
        )
        connection.commit()
        session.clear()
        flash("Password changed. Sign in with your new password.", "success")
        return redirect(url_for("login"))
    except Exception:
        if connection is not None:
            connection.rollback()
        app.logger.exception("Password recovery failed")
        flash("Unable to reset the password right now.", "danger")
        return render_template("forgot_password.html", reset_form_token=expected_csrf)
    finally:
        if connection is not None:
            connection.close()


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------


@app.route("/dashboard")
def dashboard():

    if "admin_id" not in session:
        flash("Please log in to access the dashboard.", "warning")
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = SQLiteCursor(connection)

        # 1. KYC STATISTICS
        cursor.execute("""
            SELECT
                COUNT(*) AS total_customers,

                COUNT(CASE
                    WHEN kyc_expiry_date > date('now', 'localtime', '+30 days') THEN 1
                END) AS valid_kyc,

                COUNT(CASE
                    WHEN kyc_expiry_date >= date('now', 'localtime')
                    AND kyc_expiry_date <= date('now', 'localtime', '+30 days') THEN 1
                END) AS expiring_soon,

                COUNT(CASE
                    WHEN kyc_expiry_date < date('now', 'localtime')
                    THEN 1
                END) AS expired_kyc

            FROM customers
        """)

        statistics = cursor.fetchone()

        # 2. PENDING RE-KYC SCHEDULES
        cursor.execute("""
            SELECT COUNT(*) AS pending_rekyc
            FROM rekyc_schedule
            WHERE LOWER(COALESCE(status, 'pending')) = 'pending'
        """)

        pending_result = cursor.fetchone()
        cursor.execute("""
            SELECT COUNT(*) AS total FROM joint_rekyc_schedule
            WHERE LOWER(COALESCE(status, 'Pending')) = 'pending'
        """)
        joint_pending = cursor.fetchone()["total"]
        statistics["pending_rekyc"] = pending_result["pending_rekyc"] + joint_pending

        # 3. BRANCH STATISTICS
        cursor.execute("""
            SELECT
                b.branch_name,
                b.city,
                COUNT(c.customer_id) AS total_customers,
                COUNT(CASE
                    WHEN c.kyc_expiry_date < date('now', 'localtime')
                    THEN 1
                END) AS expired_kyc,
                (SELECT COUNT(*) FROM rekyc_schedule rs
                 JOIN customers cx ON cx.customer_id = rs.customer_id
                 WHERE cx.branch_id = b.branch_id AND LOWER(COALESCE(rs.status, 'Pending'))='pending')
                + (SELECT COUNT(*) FROM joint_rekyc_schedule jrs
                   JOIN joint_account_holders jh ON jh.holder_id = jrs.holder_id
                   WHERE LOWER(COALESCE(jrs.status, 'Pending'))='pending'
                    AND EXISTS (SELECT 1 FROM customers cx
                                WHERE cx.account_number = jh.account_number AND cx.branch_id = b.branch_id))
                AS pending_rekyc
            FROM branches b
            LEFT JOIN customers c
                ON b.branch_id = c.branch_id
            GROUP BY b.branch_id, b.branch_name, b.city
            ORDER BY b.branch_name
        """)

        branch_statistics = cursor.fetchall()

        # 4. RECENT CUSTOMERS
        cursor.execute("""
            SELECT
                c.customer_id,
                c.customer_number,
                c.full_name,
                b.branch_name,
                c.kyc_expiry_date,
                CASE
                    WHEN c.kyc_expiry_date IS NULL
                        THEN 'Date Not Available'
                    WHEN c.kyc_expiry_date < date('now', 'localtime')
                        THEN 'Expired'
                    WHEN c.kyc_expiry_date <= date('now', 'localtime', '+30 days')
                        THEN 'Expiring Soon'
                    ELSE 'Valid'
                END AS expiry_status
            FROM customers c
            LEFT JOIN branches b
                ON c.branch_id = b.branch_id
            ORDER BY c.customer_id DESC
            LIMIT 5
        """)

        recent_customers = cursor.fetchall()

        # 5. MONTHLY EXPIRY CHART - NEXT SIX MONTHS
        today = date.today()
        first_month = today.replace(day=1)

        month_keys = []
        month_labels = []
        current_month = first_month

        for _ in range(6):
            month_keys.append(current_month.strftime("%Y-%m"))
            month_labels.append(current_month.strftime("%b %Y"))

            if current_month.month == 12:
                current_month = date(current_month.year + 1, 1, 1)
            else:
                current_month = date(
                    current_month.year,
                    current_month.month + 1,
                    1
                )

        end_date = current_month

        cursor.execute("""
            SELECT
                strftime('%Y-%m', kyc_expiry_date) AS month_key,
                COUNT(*) AS expiry_count
            FROM customers
            WHERE kyc_expiry_date >= ?
              AND kyc_expiry_date < ?
            GROUP BY strftime('%Y-%m', kyc_expiry_date)
            ORDER BY month_key
        """, (today, end_date))

        monthly_results = cursor.fetchall()

        monthly_lookup = {
            row["month_key"]: row["expiry_count"]
            for row in monthly_results
        }

        monthly_expiries = [
            monthly_lookup.get(key, 0)
            for key in month_keys
        ]

        # 6. IN-APP KYC NOTIFICATIONS
        cursor.execute("""
            SELECT
                customer_id,
                customer_number,
                full_name,
                kyc_expiry_date,
                CASE
                    WHEN kyc_expiry_date < date('now', 'localtime')
                        THEN 'Expired'
                    ELSE 'Expiring Soon'
                END AS notification_status,
                CAST(julianday(kyc_expiry_date) - julianday(date('now', 'localtime')) AS INTEGER) AS days_left
            FROM customers
            WHERE kyc_expiry_date IS NOT NULL
              AND kyc_expiry_date <= date('now', 'localtime', '+30 days')
            ORDER BY kyc_expiry_date ASC
        """)

        kyc_notifications = cursor.fetchall()

        # Joint holders have independent document expiry dates, even when sharing an account.
        cursor.execute("""
            SELECT holder_id, holder_name, account_number, kyc_expiry_date,
                   CASE WHEN kyc_expiry_date < date('now', 'localtime')
                        THEN 'Expired' ELSE 'Expiring Soon' END AS notification_status,
                   CAST(julianday(kyc_expiry_date) - julianday(date('now', 'localtime')) AS INTEGER) AS days_left
            FROM joint_account_holders
            WHERE kyc_expiry_date IS NOT NULL
              AND kyc_expiry_date <= date('now', 'localtime', '+30 days')
        """)
        for holder in cursor.fetchall():
            kyc_notifications.append({
                "customer_id": None,
                "customer_number": "Account " + holder["account_number"],
                "full_name": holder["holder_name"] + " (Joint Holder)",
                "kyc_expiry_date": holder["kyc_expiry_date"],
                "notification_status": holder["notification_status"],
                "days_left": holder["days_left"],
                "holder_id": holder["holder_id"],
            })
        kyc_notifications.sort(key=lambda item: item["kyc_expiry_date"] or date.max)

        notification_count = len(kyc_notifications)

        return render_template(
            "dashboard.html",
            statistics=statistics,
            branch_statistics=branch_statistics,
            recent_customers=recent_customers,
            monthly_labels=month_labels,
            monthly_expiries=monthly_expiries,
            kyc_notifications=kyc_notifications,
            notification_count=notification_count,
            today=today.strftime("%d %B %Y")
        )

    except Exception:
        app.logger.exception("Dashboard loading failed")
        return (
            "Unable to load dashboard data. "
            "Please check the VS Code terminal."
        ), 500

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()


@app.route("/customers", methods=["GET"])
def customers():

    # Only logged-in admins can view customers
    if "admin_id" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = SQLiteCursor(connection)

        search_query = request.args.get("q", "").strip()[:100]
        search_pattern = f"%{search_query}%"

        cursor.execute("""
            SELECT
                c.customer_id,
                c.customer_number,
                c.full_name,
                c.phone,
                c.email,
                c.account_number,
                c.account_type,
                c.kyc_document,
                c.kyc_issue_date,
                c.kyc_expiry_date,
                c.kyc_status,
                c.branch_id,
                b.branch_name,
                b.city
            FROM customers c
            LEFT JOIN branches b
                ON c.branch_id = b.branch_id
            WHERE (? = '' OR c.full_name LIKE ? COLLATE NOCASE
                   OR c.customer_number LIKE ? COLLATE NOCASE
                   OR c.account_number LIKE ? COLLATE NOCASE
                   OR c.kyc_document LIKE ? COLLATE NOCASE)
            ORDER BY c.customer_id DESC
        """, (search_query, search_pattern, search_pattern,
              search_pattern, search_pattern))

        customers_list = cursor.fetchall()

        today = date.today()

        # Calculate current KYC status
        for customer in customers_list:
            expiry_date = customer.get("kyc_expiry_date")

            customer["kyc_status"] = kyc_status_for(expiry_date)

        return render_template(
            "customers.html",
            search_query=search_query,
            customers=customers_list
        )

    except Exception:
        app.logger.exception("Customers page loading failed")
        flash("Unable to load customers. Please check the terminal.", "danger")
        return redirect(url_for("dashboard"))

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

# --------------------------------------------------
# ADD NEW CUSTOMER
# --------------------------------------------------

@app.route("/customers/add", methods=["GET", "POST"])
def add_customer():

    # Only logged-in admins can add customers
    if "admin_id" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = SQLiteCursor(connection)

        # Load branches for the dropdown
        cursor.execute("""
            SELECT branch_id, branch_name, city
            FROM branches
            ORDER BY branch_name
        """)

        branches = cursor.fetchall()

        # Process submitted form
        if request.method == "POST":

            customer_number = request.form.get(
                "customer_number", ""
            ).strip()

            full_name = request.form.get(
                "full_name", ""
            ).strip()

            dob_text = request.form.get("dob", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()

            branch_text = request.form.get(
                "branch_id", ""
            ).strip()

            account_type = request.form.get(
                "account_type", ""
            ).strip()

            account_number = request.form.get(
                "account_number", ""
            ).strip()

            kyc_document = request.form.get(
                "kyc_document", ""
            ).strip()

            issue_text = request.form.get(
                "kyc_issue_date", ""
            ).strip()

            expiry_text = request.form.get(
                "kyc_expiry_date", ""
            ).strip()

            # Check required fields
            if not all([
                customer_number,
                full_name,
                phone,
                branch_text,
                account_number,
                kyc_document,
                issue_text,
                expiry_text
            ]):
                flash("Please fill in all required fields.", "warning")
                return render_template(
                    "add_customer.html",
                    branches=branches
                )

            # Validate branch selection
            try:
                branch_id = int(branch_text)
            except ValueError:
                flash("Please select a valid branch.", "warning")
                return render_template(
                    "add_customer.html",
                    branches=branches
                )

            if not any(
                int(branch["branch_id"]) == branch_id
                for branch in branches
            ):
                flash("Selected branch does not exist.", "warning")
                return render_template(
                    "add_customer.html",
                    branches=branches
                )

            # Convert HTML date values into Python dates
            try:
                dob = parse_kyc_date(dob_text) if dob_text else None
                kyc_issue_date = date.fromisoformat(issue_text)
                kyc_expiry_date = date.fromisoformat(expiry_text)

            except ValueError:
                flash("Please enter valid dates.", "warning")
                return render_template(
                    "add_customer.html",
                    branches=branches
                )

            # Validate dates
            if dob and dob > date.today():
                flash("Date of birth cannot be in the future.", "warning")
                return render_template(
                    "add_customer.html",
                    branches=branches
                )

            if kyc_expiry_date < kyc_issue_date:
                flash(
                    "KYC expiry date cannot be before issue date.",
                    "warning"
                )
                return render_template(
                    "add_customer.html",
                    branches=branches
                )

            # Calculate KYC status automatically
            today = date.today()

            kyc_status = kyc_status_for(kyc_expiry_date)

            # Insert customer into SQLite
            cursor.execute("""
                INSERT INTO customers (
                    customer_number,
                    full_name,
                    dob,
                    phone,
                    email,
                    branch_id,
                    account_type,
                    account_number,
                    kyc_document,
                    kyc_issue_date,
                    kyc_expiry_date,
                    kyc_status
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
            """, (
                customer_number,
                full_name,
                dob,
                phone,
                email or None,
                branch_id,
                account_type or None,
                account_number,
                kyc_document,
                kyc_issue_date,
                kyc_expiry_date,
                kyc_status
            ))

            connection.commit()

            flash(
                "Customer added successfully!",
                "success"
            )

            return redirect(url_for("customers"))

        return render_template(
            "add_customer.html",
            branches=branches
        )

    except Exception:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Add customer failed")

        flash(
            "Unable to add customer. Please check the VS Code terminal.",
            "danger"
        )

        return redirect(url_for("customers"))

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

# --------------------------------------------------
# EDIT EXISTING CUSTOMER
# --------------------------------------------------
@app.route("/customers/edit/<int:customer_id>", methods=["GET", "POST"])
def edit_customer(customer_id):

    if "admin_id" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = SQLiteCursor(connection)

        # Load branch details for the dropdown
        cursor.execute("""
            SELECT branch_id, branch_name, city
            FROM branches
            ORDER BY branch_name
        """)
        branches = cursor.fetchall()

        # Find the existing customer
        cursor.execute("""
            SELECT *
            FROM customers
            WHERE customer_id = ?
        """, (customer_id,))

        customer = cursor.fetchone()

        if not customer:
            flash("Customer record not found.", "warning")
            return redirect(url_for("customers"))

        # Process the edit form
        if request.method == "POST":

            customer_number = request.form.get("customer_number", "").strip()
            full_name = request.form.get("full_name", "").strip()
            dob_text = request.form.get("dob", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()
            branch_text = request.form.get("branch_id", "").strip()
            account_type = request.form.get("account_type", "").strip()
            account_number = request.form.get("account_number", "").strip()
            kyc_document = request.form.get("kyc_document", "").strip()
            issue_text = request.form.get("kyc_issue_date", "").strip()
            expiry_text = request.form.get("kyc_expiry_date", "").strip()

            # Validate required fields
            if not all([
                customer_number, full_name, phone, branch_text,
                account_number, kyc_document, issue_text, expiry_text
            ]):
                flash("Please fill in all required fields.", "warning")
                return render_template(
                    "edit_customer.html",
                    customer=customer,
                    branches=branches
                )

            # Validate branch
            try:
                branch_id = int(branch_text)
            except ValueError:
                flash("Please select a valid branch.", "warning")
                return render_template(
                    "edit_customer.html",
                    customer=customer,
                    branches=branches
                )

            if not any(
                int(branch["branch_id"]) == branch_id
                for branch in branches
            ):
                flash("Selected branch does not exist.", "warning")
                return render_template(
                    "edit_customer.html",
                    customer=customer,
                    branches=branches
                )

            # Convert dates
            try:
                dob = parse_kyc_date(dob_text) if dob_text else None
                kyc_issue_date = date.fromisoformat(issue_text)
                kyc_expiry_date = date.fromisoformat(expiry_text)
            except ValueError:
                flash("Please enter valid dates.", "warning")
                return render_template(
                    "edit_customer.html",
                    customer=customer,
                    branches=branches
                )

            # Validate dates
            if dob and dob > date.today():
                flash("Date of birth cannot be in the future.", "warning")
                return render_template(
                    "edit_customer.html",
                    customer=customer,
                    branches=branches
                )

            if kyc_expiry_date < kyc_issue_date:
                flash("KYC expiry date cannot be before issue date.", "warning")
                return render_template(
                    "edit_customer.html",
                    customer=customer,
                    branches=branches
                )

            # Calculate KYC status
            today = date.today()

            kyc_status = kyc_status_for(kyc_expiry_date)

            old_account_number = customer["account_number"]
            if old_account_number != account_number:
                another_account_owner = connection.execute(
                    "SELECT 1 FROM customers WHERE account_number = ? AND customer_id != ? LIMIT 1",
                    (old_account_number, customer_id)
                ).fetchone()
                if not another_account_owner:
                    connection.execute(
                        "UPDATE joint_account_holders SET account_number = ? WHERE account_number = ?",
                        (account_number, old_account_number)
                    )

            # Update existing customer
            cursor.execute("""
                UPDATE customers
                SET
                    customer_number = ?,
                    full_name = ?,
                    dob = ?,
                    phone = ?,
                    email = ?,
                    branch_id = ?,
                    account_type = ?,
                    account_number = ?,
                    kyc_document = ?,
                    kyc_issue_date = ?,
                    kyc_expiry_date = ?,
                    kyc_status = ?
                WHERE customer_id = ?
            """, (
                customer_number,
                full_name,
                dob,
                phone,
                email or None,
                branch_id,
                account_type or None,
                account_number,
                kyc_document,
                kyc_issue_date,
                kyc_expiry_date,
                kyc_status,
                customer_id
            ))

            connection.commit()

            flash("Customer details updated successfully!", "success")
            return redirect(url_for("customers"))

        # Show existing customer details in the form
        return render_template(
            "edit_customer.html",
            customer=customer,
            branches=branches
        )

    except Exception:
        if connection is not None:
            connection.rollback()

        app.logger.exception("Edit customer failed")
        flash("Unable to update customer. Check the VS Code terminal.", "danger")
        return redirect(url_for("customers"))

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None:
            connection.close()

@app.route("/customers/view/<int:customer_id>")
def view_customer(customer_id):
    if "admin_id" not in session:
        return redirect(url_for("login"))
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)
        cursor.execute("""SELECT c.*, b.branch_name FROM customers c
                          LEFT JOIN branches b ON c.branch_id = b.branch_id
                          WHERE c.customer_id = ?""", (customer_id,))
        customer = cursor.fetchone()
        if customer is None:
            flash("Customer not found.", "warning")
            return redirect(url_for("customers"))
        return render_template("view_customer.html", customer=customer)
    except Exception:
        app.logger.exception("View customer failed")
        flash("Unable to view customer.", "danger")
        return redirect(url_for("customers"))
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

@app.route("/customers/delete/<int:customer_id>", methods=["POST"])
def delete_customer(customer_id):

    if "admin_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = SQLiteCursor(connection)

    try:
        owner = connection.execute("SELECT account_number FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
        if owner:
            owner_count = connection.execute("SELECT COUNT(*) FROM customers WHERE account_number = ?", (owner["account_number"],)).fetchone()[0]
            holder_count = connection.execute("SELECT COUNT(*) FROM joint_account_holders WHERE account_number = ?", (owner["account_number"],)).fetchone()[0]
            if owner_count == 1 and holder_count:
                flash("Remove or reassign joint holders before deleting the last customer for this account.", "warning")
                return redirect(url_for("customers"))

        cursor.execute(
            "DELETE FROM customers WHERE customer_id = ?",
            (customer_id,)
        )

        connection.commit()

        flash("Customer deleted successfully!", "success")

    except Exception as e:
        connection.rollback()
        print("Delete Customer Error:", e)
        flash("Unable to delete customer. Related records may exist.", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("customers"))
# ==========================================
# BRANCH MANAGEMENT
# ==========================================

@app.route("/branches")
def branches():

    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        cursor.execute("""
            SELECT
                branch_id,
                branch_code,
                branch_name,
                city
            FROM branches
            ORDER BY branch_id DESC
        """)

        branch_list = cursor.fetchall()

        return render_template(
            "branches.html",
            branches=branch_list
        )

    except Exception as e:
        print("Branch loading error:", e)
        flash("Unable to load branch records.", "danger")
        return redirect(url_for("dashboard"))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# ==========================================
# ADD NEW BRANCH
# ==========================================

@app.route("/branches/add", methods=["GET", "POST"])
def add_branch():

    if "admin_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        branch_code = request.form.get("branch_code", "").strip()
        branch_name = request.form.get("branch_name", "").strip()
        city = request.form.get("city", "").strip()

        if not branch_code or not branch_name or not city:
            flash("Please fill in all branch details.", "warning")
            return render_template("add_branch.html")

        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = SQLiteCursor(conn)

            # Check whether branch code already exists
            cursor.execute(
                "SELECT branch_id FROM branches WHERE branch_code = ?",
                (branch_code,)
            )

            existing_branch = cursor.fetchone()

            if existing_branch:
                flash("This branch code already exists.", "warning")
                return render_template("add_branch.html")

            # Insert new branch
            cursor.execute(
                """
                INSERT INTO branches
                (branch_code, branch_name, city)
                VALUES (?, ?, ?)
                """,
                (branch_code, branch_name, city)
            )

            conn.commit()

            flash("New branch added successfully!", "success")
            return redirect(url_for("branches"))

        except Exception as e:
            if conn:
                conn.rollback()

            print("Add branch error:", e)
            flash("Unable to add branch. Please check the details.", "danger")

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template("add_branch.html")

@app.route("/branches/edit/<int:branch_id>", methods=["GET", "POST"])
def edit_branch(branch_id):

    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = SQLiteCursor(conn)

    try:
        # Get existing branch
        cursor.execute(
            """
            SELECT branch_id, branch_code, branch_name, city
            FROM branches
            WHERE branch_id = ?
            """,
            (branch_id,)
        )

        branch = cursor.fetchone()

        if not branch:
            flash("Branch not found.", "danger")
            return redirect(url_for("branches"))

        if request.method == "POST":

            branch_code = request.form.get("branch_code", "").strip()
            branch_name = request.form.get("branch_name", "").strip()
            city = request.form.get("city", "").strip()

            if not branch_code or not branch_name or not city:
                flash("Please fill in all fields.", "warning")
                return render_template(
                    "edit_branch.html",
                    branch=branch
                )

            # Check duplicate branch code, excluding current branch
            cursor.execute(
                """
                SELECT branch_id
                FROM branches
                WHERE branch_code = ? AND branch_id != ?
                """,
                (branch_code, branch_id)
            )

            duplicate = cursor.fetchone()

            if duplicate:
                flash("This branch code already exists.", "danger")
                return render_template(
                    "edit_branch.html",
                    branch=branch
                )

            # Update branch
            cursor.execute(
                """
                UPDATE branches
                SET branch_code = ?,
                    branch_name = ?,
                    city = ?
                WHERE branch_id = ?
                """,
                (branch_code, branch_name, city, branch_id)
            )

            conn.commit()

            flash("Branch details updated successfully!", "success")
            return redirect(url_for("branches"))

        return render_template("edit_branch.html", branch=branch)

    except Exception as e:
        conn.rollback()
        print("Edit Branch Error:", e)
        flash("Unable to update branch. Please try again.", "danger")
        return redirect(url_for("branches"))

    finally:
        cursor.close()
        conn.close()

@app.route("/branches/delete/<int:branch_id>", methods=["POST"])
def delete_branch(branch_id):

    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = SQLiteCursor(conn)

    try:
        # Check whether branch exists
        cursor.execute(
            "SELECT branch_id, branch_name FROM branches WHERE branch_id = ?",
            (branch_id,)
        )

        branch = cursor.fetchone()

        if not branch:
            flash("Branch not found.", "danger")
            return redirect(url_for("branches"))

        # Check whether customers are linked to this branch
        cursor.execute(
            "SELECT COUNT(*) AS customer_count FROM customers WHERE branch_id = ?",
            (branch_id,)
        )

        result = cursor.fetchone()

        if result["customer_count"] > 0:
            flash(
                "This branch cannot be deleted because customers are linked to it. "
                "Please reassign those customers to another branch first.",
                "warning"
            )
            return redirect(url_for("branches"))

        # Delete branch
        cursor.execute(
            "DELETE FROM branches WHERE branch_id = ?",
            (branch_id,)
        )

        conn.commit()

        flash(
            f"Branch '{branch['branch_name']}' deleted successfully!",
            "success"
        )

    except Exception as e:
        conn.rollback()
        print("Delete Branch Error:", e)

        flash(
            "Unable to delete this branch. It may be linked to other records.",
            "danger"
        )

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("branches"))


# --------------------------------------------------
# JOINT ACCOUNT HOLDERS - VIEW
# --------------------------------------------------

@app.route("/joint-holders")
def joint_holders():

    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        cursor.execute("""
            SELECT
                holder_id,
                account_number,
                holder_name,
                dob,
                phone,
                email,
                kyc_document,
                kyc_issue_date,
                kyc_expiry_date,
                kyc_status
            FROM joint_account_holders
            ORDER BY holder_id DESC
        """)

        holders = cursor.fetchall()

        cursor.execute("""
            SELECT holder_id FROM joint_rekyc_schedule
            WHERE LOWER(COALESCE(status, 'Pending')) = 'pending'
        """)
        pending_holder_ids = {row["holder_id"] for row in cursor.fetchall()}
        for holder in holders:
            holder["has_pending_schedule"] = holder["holder_id"] in pending_holder_ids

        today = date.today()

        for holder in holders:

            expiry_date = holder["kyc_expiry_date"]

            holder["display_status"] = kyc_status_for(expiry_date) if expiry_date else "Not Available"

        return render_template(
            "joint_holders.html",
            holders=holders
        )

    except Exception:
        app.logger.exception("Joint Account Holders Page Error")
        flash("Unable to load joint account holders.", "danger")
        return redirect(url_for("dashboard"))

    finally:

        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()


# --------------------------------------------------
# ADD JOINT ACCOUNT HOLDER
# --------------------------------------------------

@app.route("/joint-holders/add", methods=["GET", "POST"])
def add_joint_holder():

    if "admin_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        conn = None
        cursor = None

        try:

            # GET FORM DATA
            account_number = request.form.get(
                "account_number", ""
            ).strip()

            holder_name = request.form.get(
                "holder_name", ""
            ).strip()

            phone = request.form.get(
                "phone", ""
            ).strip()

            email = request.form.get(
                "email", ""
            ).strip() or None

            kyc_document = request.form.get(
                "kyc_document", ""
            ).strip()

            dob = parse_kyc_date(
                request.form["dob"]
            )

            issue_date = date.fromisoformat(
                request.form["kyc_issue_date"]
            )

            expiry_date = date.fromisoformat(
                request.form["kyc_expiry_date"]
            )

            # VALIDATION
            if not account_number or not holder_name or not phone or not kyc_document:
                flash("Please fill all required fields.", "danger")
                return redirect(url_for("add_joint_holder"))

            if not phone.isdigit() or len(phone) != 10:
                flash("Enter a valid 10-digit phone number.", "danger")
                return redirect(url_for("add_joint_holder"))

            if dob > date.today():
                flash("Date of birth cannot be in the future.", "danger")
                return redirect(url_for("add_joint_holder"))

            if expiry_date < issue_date:
                flash("Expiry date cannot be before issue date.", "danger")
                return redirect(url_for("add_joint_holder"))

            # AUTOMATIC KYC STATUS
            today = date.today()

            days_remaining = (expiry_date - today).days

            kyc_status = kyc_status_for(expiry_date)

            # DATABASE CONNECTION
            conn = get_db_connection()
            cursor = SQLiteCursor(conn)

            if not verify_joint_account(conn, account_number):
                flash("Account number not found. Add the customer account before registering a joint holder.", "warning")
                return redirect(url_for("add_joint_holder"))

            # INSERT HOLDER DETAILS
            cursor.execute("""
                INSERT INTO joint_account_holders
                (
                    account_number,
                    holder_name,
                    dob,
                    phone,
                    email,
                    kyc_document,
                    kyc_issue_date,
                    kyc_expiry_date,
                    kyc_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account_number,
                holder_name,
                dob,
                phone,
                email,
                kyc_document,
                issue_date,
                expiry_date,
                kyc_status
            ))

            conn.commit()

            flash(
                "Joint Account Holder added successfully!",
                "success"
            )

            return redirect(url_for("joint_holders"))

        except ValueError:

            flash(
                "Please enter valid dates in all date fields.",
                "danger"
            )

        except Exception:

            if conn is not None:
                conn.rollback()

            app.logger.exception("Add Joint Holder Error")

            flash(
                "Unable to add joint account holder. Check the terminal error.",
                "danger"
            )

        finally:

            if cursor is not None:
                cursor.close()

            if conn is not None:
                conn.close()

    return render_template("add_joint_holder.html")

@app.route("/joint-holders/edit/<int:holder_id>", methods=["GET", "POST"])
def edit_joint_holder(holder_id):

    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        if request.method == "POST":

            account_number = request.form.get("account_number", "").strip()
            holder_name = request.form.get("holder_name", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip() or None
            kyc_document = request.form.get("kyc_document", "").strip()

            dob = parse_kyc_date(request.form["dob"])
            issue_date = date.fromisoformat(request.form["kyc_issue_date"])
            expiry_date = date.fromisoformat(request.form["kyc_expiry_date"])

            if not account_number or not holder_name or not phone or not kyc_document:
                flash("Please fill in all required fields.", "danger")
                return redirect(url_for("edit_joint_holder", holder_id=holder_id))

            if len(phone) != 10 or not phone.isdigit():
                flash("Enter a valid 10-digit phone number.", "danger")
                return redirect(url_for("edit_joint_holder", holder_id=holder_id))

            if dob > date.today():
                flash("Date of birth cannot be in the future.", "danger")
                return redirect(url_for("edit_joint_holder", holder_id=holder_id))

            if expiry_date < issue_date:
                flash("KYC expiry date cannot be before issue date.", "danger")
                return redirect(url_for("edit_joint_holder", holder_id=holder_id))

            days_remaining = (expiry_date - date.today()).days

            kyc_status = kyc_status_for(expiry_date)

            if not verify_joint_account(conn, account_number):
                flash("Account number not found in customer records.", "warning")
                return redirect(url_for("edit_joint_holder", holder_id=holder_id))

            cursor.execute("""
                UPDATE joint_account_holders
                SET account_number = ?,
                    holder_name = ?,
                    dob = ?,
                    phone = ?,
                    email = ?,
                    kyc_document = ?,
                    kyc_issue_date = ?,
                    kyc_expiry_date = ?,
                    kyc_status = ?
                WHERE holder_id = ?
            """, (
                account_number,
                holder_name,
                dob,
                phone,
                email,
                kyc_document,
                issue_date,
                expiry_date,
                kyc_status,
                holder_id
            ))

            conn.commit()

            flash("Joint account holder updated successfully!", "success")
            return redirect(url_for("joint_holders"))

        cursor.execute("""
            SELECT *
            FROM joint_account_holders
            WHERE holder_id = ?
        """, (holder_id,))

        holder = cursor.fetchone()

        if holder is None:
            flash("Joint account holder not found.", "danger")
            return redirect(url_for("joint_holders"))

        return render_template(
            "edit_joint_holder.html",
            holder=holder
        )

    except Exception:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Edit Joint Holder Error")
        flash("Unable to update joint account holder. Check the terminal for details.", "danger")
        return redirect(url_for("joint_holders"))

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()
@app.route("/joint-holders/delete/<int:holder_id>", methods=["POST"])
def delete_joint_holder(holder_id):

    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        cursor.execute("""
            DELETE FROM joint_account_holders
            WHERE holder_id = ?
        """, (holder_id,))

        if cursor.rowcount == 0:
            flash("Joint account holder not found.", "warning")
        else:
            conn.commit()
            flash("Joint account holder deleted successfully!", "success")

    except Exception:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Delete Joint Holder Error")
        flash("Unable to delete joint account holder.", "danger")

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()

    return redirect(url_for("joint_holders"))

@app.route("/reports/monthly")
def monthly_kyc_report():

    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    # Default month is the current month
    selected_month = request.args.get(
        "month",
        date.today().strftime("%Y-%m")
    )

    branch_id = request.args.get("branch_id", "")

    # Validate selected month
    try:
        year, month = map(int, selected_month.split("-"))
        if not (1 <= month <= 12 and year >= 2000):
            raise ValueError
    except (ValueError, AttributeError):
        selected_month = date.today().strftime("%Y-%m")

    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        # Load branches for the filter
        cursor.execute("""
            SELECT branch_id, branch_name
            FROM branches
            ORDER BY branch_name
        """)
        branches = cursor.fetchall()

        # Monthly customer expiry report
        query = """
            SELECT
                c.customer_id,
                c.customer_number,
                c.full_name,
                c.phone,
                c.email,
                c.account_number,
                c.account_type,
                c.kyc_expiry_date,
                b.branch_name,
                b.city
            FROM customers AS c
            LEFT JOIN branches AS b
                ON c.branch_id = b.branch_id
            WHERE strftime('%Y-%m', c.kyc_expiry_date) = ?
        """

        params = [selected_month]

        # Optional branch filter
        if branch_id:
            try:
                branch_id = int(branch_id)
                query += " AND c.branch_id = ?"
                params.append(branch_id)
            except ValueError:
                branch_id = ""

        query += " ORDER BY c.kyc_expiry_date ASC"

        cursor.execute(query, tuple(params))
        customers = cursor.fetchall()

        # Calculate current KYC status
        today = date.today()

        expired_count = 0
        expiring_count = 0
        valid_count = 0

        for customer in customers:
            expiry_date = customer["kyc_expiry_date"]

            customer["status"] = kyc_status_for(expiry_date)
            customer["days_left"] = (expiry_date - today).days if expiry_date else None
            if customer["status"] == "Expired":
                expired_count += 1
            elif customer["status"] == "Expiring Soon":
                expiring_count += 1
            elif customer["status"] == "Valid":
                valid_count += 1

        return render_template(
            "monthly_kyc_report.html",
            customers=customers,
            branches=branches,
            selected_month=selected_month,
            selected_branch=branch_id,
            total_count=len(customers),
            expired_count=expired_count,
            expiring_count=expiring_count,
            valid_count=valid_count
        )

    except Exception:
        app.logger.exception("Monthly KYC Report Error")
        flash("Unable to load the monthly KYC report.", "danger")
        return redirect(url_for("dashboard"))

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()


@app.route("/reports/monthly/export")
def export_monthly_kyc_report():

    # Check admin login
    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    selected_month = request.args.get(
        "month",
        date.today().strftime("%Y-%m")
    )

    branch_id = request.args.get("branch_id", "")

    # Validate reporting month
    try:
        year, month = map(int, selected_month.split("-"))

        if not (1 <= month <= 12 and year >= 2000):
            raise ValueError

    except (ValueError, AttributeError):
        flash("Invalid reporting month.", "warning")
        return redirect(url_for("monthly_kyc_report"))

    try:
        # Database connection
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        # Monthly customer query
        query = """
            SELECT
                c.customer_number,
                c.full_name,
                c.phone,
                c.email,
                c.account_number,
                c.account_type,
                c.kyc_expiry_date,
                b.branch_name,
                b.city
            FROM customers AS c
            LEFT JOIN branches AS b
                ON c.branch_id = b.branch_id
            WHERE strftime('%Y-%m', c.kyc_expiry_date) = ?
        """

        params = [selected_month]

        # Optional branch filter
        if branch_id:
            try:
                branch_id = int(branch_id)

                query += " AND c.branch_id = ?"
                params.append(branch_id)

            except ValueError:
                flash("Invalid branch selection.", "warning")
                return redirect(url_for("monthly_kyc_report"))

        query += " ORDER BY c.kyc_expiry_date ASC"

        cursor.execute(query, tuple(params))
        customers = cursor.fetchall()

        # Create Excel workbook
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Monthly KYC Report"

        # Report heading
        sheet.merge_cells("A1:J1")

        sheet["A1"] = "MONTHLY KYC EXPIRY REPORT"
        sheet["A1"].font = Font(
            bold=True,
            size=16,
            color="FFFFFF"
        )
        sheet["A1"].fill = PatternFill(
            fill_type="solid",
            fgColor="142B4A"
        )
        sheet["A1"].alignment = Alignment(
            horizontal="center",
            vertical="center"
        )

        sheet.row_dimensions[1].height = 30

        # Reporting month
        sheet.merge_cells("A2:J2")

        sheet["A2"] = f"Reporting Month: {selected_month}"
        sheet["A2"].font = Font(
            bold=True,
            size=11,
            color="142B4A"
        )
        sheet["A2"].alignment = Alignment(
            horizontal="left"
        )

        # Table headers
        headers = [
            "S.No",
            "Customer Number",
            "Customer Name",
            "Phone",
            "Email",
            "Account Number",
            "Account Type",
            "Branch",
            "City",
            "KYC Expiry Date"
        ]

        header_row = 4

        for col_num, heading in enumerate(headers, start=1):

            cell = sheet.cell(
                row=header_row,
                column=col_num,
                value=heading
            )

            cell.font = Font(
                bold=True,
                color="FFFFFF"
            )

            cell.fill = PatternFill(
                fill_type="solid",
                fgColor="2463A6"
            )

            cell.alignment = Alignment(
                horizontal="center",
                vertical="center"
            )

        sheet.row_dimensions[header_row].height = 25

        # Customer records
        for index, customer in enumerate(customers, start=1):

            row = [
                index,
                customer["customer_number"],
                customer["full_name"],
                customer["phone"],
                customer["email"],
                customer["account_number"],
                customer["account_type"],
                customer["branch_name"] or "Not Assigned",
                customer["city"] or "",
                customer["kyc_expiry_date"]
            ]

            for col_num, value in enumerate(row, start=1):

                cell = sheet.cell(
                    row=header_row + index,
                    column=col_num,
                    value=value
                )

                cell.alignment = Alignment(
                    vertical="center"
                )

                # Format KYC expiry date
                if col_num == 10 and value:
                    cell.number_format = "DD-MM-YYYY"

        # Automatically adjust Excel column widths
        widths = [10, 20, 25, 16, 28, 20, 17, 24, 18, 20]

        for index, width in enumerate(widths, start=1):
            column_letter = get_column_letter(index)
            sheet.column_dimensions[column_letter].width = width

        # Freeze header rows
        sheet.freeze_panes = "A5"

        # Add table filter
        if customers:
            sheet.auto_filter.ref = (
                f"A4:J{header_row + len(customers)}"
            )

        # Create Excel file in memory
        output = BytesIO()

        workbook.save(output)
        output.seek(0)

        filename = f"KYC_Monthly_Report_{selected_month}.xlsx"

        # Download Excel file
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

    except Exception:
        app.logger.exception("Excel Report Export Error")

        flash(
            "Unable to export the Excel report. Please try again.",
            "danger"
        )

        return redirect(url_for("monthly_kyc_report"))

    finally:

        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()

@app.route("/reports/branch-wise")
def branch_wise_report():

    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    selected_branch = request.args.get("branch_id", "")
    selected_status = request.args.get("status", "")

    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        # Get all branches for the filter
        cursor.execute("""
            SELECT branch_id, branch_code, branch_name, city
            FROM branches
            ORDER BY branch_name
        """)
        branches = cursor.fetchall()

        # Get customer records
        query = """
            SELECT
                c.customer_id,
                c.customer_number,
                c.full_name,
                c.phone,
                c.account_number,
                c.kyc_expiry_date,
                b.branch_name,
                b.city,
                (SELECT COUNT(*) FROM rekyc_schedule rs
                 WHERE rs.customer_id = c.customer_id
                   AND LOWER(COALESCE(rs.status, 'Pending')) = 'pending')
                + (SELECT COUNT(*) FROM joint_rekyc_schedule jrs
                   JOIN joint_account_holders jh ON jh.holder_id = jrs.holder_id
                   WHERE jh.account_number = c.account_number
                     AND LOWER(COALESCE(jrs.status, 'Pending')) = 'pending') AS pending_rekyc
            FROM customers c
            LEFT JOIN branches b
                ON c.branch_id = b.branch_id
            WHERE 1 = 1
        """

        params = []

        if selected_branch:
            try:
                selected_branch = int(selected_branch)
                query += " AND c.branch_id = ?"
                params.append(selected_branch)
            except ValueError:
                flash("Invalid branch selection.", "warning")
                return redirect(url_for("branch_wise_report"))

        query += " ORDER BY b.branch_name, c.full_name"

        cursor.execute(query, tuple(params))
        records = cursor.fetchall()

        today = date.today()
        customers = []

        for customer in records:
            expiry = customer["kyc_expiry_date"]

            status = kyc_status_for(expiry) if expiry else "Not Set"
            days_left = (expiry - today).days if expiry else None

            customer["status"] = status
            customer["days_left"] = days_left

            if selected_status == "Pending Re-KYC":
                if not customer["pending_rekyc"]:
                    continue
            elif selected_status and status != selected_status:
                continue

            customers.append(customer)

        total_count = len(customers)
        expired_count = sum(
            1 for c in customers if c["status"] == "Expired"
        )
        expiring_count = sum(
            1 for c in customers if c["status"] == "Expiring Soon"
        )
        valid_count = sum(
            1 for c in customers if c["status"] == "Valid"
        )

        pending_count = sum(c["pending_rekyc"] for c in customers)
        branch_pending_summary = {}
        for item in customers:
            key = item["branch_name"] or "Unassigned"
            branch_pending_summary[key] = branch_pending_summary.get(key, 0) + item["pending_rekyc"]

        return render_template(
            "branch_wise_report.html",
            branches=branches,
            customers=customers,
            selected_branch=selected_branch,
            selected_status=selected_status,
            total_count=total_count,
            expired_count=expired_count,
            expiring_count=expiring_count,
            valid_count=valid_count,
            pending_count=pending_count,
            branch_pending_summary=branch_pending_summary
        )

    except Exception:
        app.logger.exception("Branch-wise Report Error")
        flash("Unable to load the branch-wise report.", "danger")
        return redirect(url_for("dashboard"))

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()

@app.route("/reports/branch-wise/export")
def export_branch_wise_report():

    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    selected_branch = request.args.get("branch_id", "")
    selected_status = request.args.get("status", "")

    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        query = """
            SELECT
                c.customer_number,
                c.full_name,
                c.phone,
                c.account_number,
                c.kyc_expiry_date,
                b.branch_name,
                b.city,
                (SELECT COUNT(*) FROM rekyc_schedule rs
                 WHERE rs.customer_id = c.customer_id
                   AND LOWER(COALESCE(rs.status, 'Pending')) = 'pending')
                + (SELECT COUNT(*) FROM joint_rekyc_schedule jrs
                   JOIN joint_account_holders jh ON jh.holder_id = jrs.holder_id
                   WHERE jh.account_number = c.account_number
                     AND LOWER(COALESCE(jrs.status, 'Pending')) = 'pending') AS pending_rekyc
            FROM customers c
            LEFT JOIN branches b
                ON c.branch_id = b.branch_id
            WHERE 1 = 1
        """

        params = []

        if selected_branch:
            try:
                selected_branch = int(selected_branch)
                query += " AND c.branch_id = ?"
                params.append(selected_branch)
            except ValueError:
                flash("Invalid branch selection.", "warning")
                return redirect(url_for("branch_wise_report"))

        query += " ORDER BY b.branch_name, c.full_name"

        cursor.execute(query, tuple(params))
        records = cursor.fetchall()

        today = date.today()
        customers = []

        for customer in records:

            expiry = customer["kyc_expiry_date"]

            status = kyc_status_for(expiry) if expiry else "Not Set"
            days_left = (expiry - today).days if expiry else None

            if selected_status == "Pending Re-KYC":
                if not customer["pending_rekyc"]:
                    continue
            elif selected_status and status != selected_status:
                continue

            customer["status"] = status
            customer["days_left"] = days_left
            customers.append(customer)

        # Create Excel workbook
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Branch KYC Report"

        # Report heading
        sheet.merge_cells("A1:K1")
        sheet["A1"] = "BRANCH-WISE KYC REPORT"
        sheet["A1"].font = Font(
            bold=True,
            size=16,
            color="FFFFFF"
        )
        sheet["A1"].fill = PatternFill(
            fill_type="solid",
            fgColor="142B4A"
        )
        sheet["A1"].alignment = Alignment(
            horizontal="center",
            vertical="center"
        )
        sheet.row_dimensions[1].height = 30

        # Filter information
        sheet.merge_cells("A2:K2")

        branch_label = (
            f"Branch ID: {selected_branch}"
            if selected_branch else "All Branches"
        )

        status_label = selected_status or "All Statuses"

        sheet["A2"] = (
            f"Branch: {branch_label} | KYC Status: {status_label}"
        )
        sheet["A2"].font = Font(
            bold=True,
            size=11,
            color="142B4A"
        )

        # Column headings
        headers = [
            "S.No",
            "Customer Number",
            "Customer Name",
            "Phone",
            "Account Number",
            "Branch",
            "City",
            "KYC Expiry Date",
            "Days Left",
            "KYC Status",
            "Pending Re-KYC"
        ]

        header_row = 4

        for col_num, heading in enumerate(headers, start=1):
            cell = sheet.cell(
                row=header_row,
                column=col_num,
                value=heading
            )
            cell.font = Font(
                bold=True,
                color="FFFFFF"
            )
            cell.fill = PatternFill(
                fill_type="solid",
                fgColor="2463A6"
            )
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center"
            )

        sheet.row_dimensions[header_row].height = 25

        # Add customer records
        for index, customer in enumerate(customers, start=1):

            row = [
                index,
                customer["customer_number"],
                customer["full_name"],
                customer["phone"],
                customer["account_number"],
                customer["branch_name"] or "Not Assigned",
                customer["city"] or "",
                customer["kyc_expiry_date"],
                customer["days_left"],
                customer["status"],
                "Pending" if customer["pending_rekyc"] else "None"
            ]

            for col_num, value in enumerate(row, start=1):
                cell = sheet.cell(
                    row=header_row + index,
                    column=col_num,
                    value=value
                )

                cell.alignment = Alignment(
                    vertical="center"
                )

                if col_num == 8 and value:
                    cell.number_format = "DD-MM-YYYY"

        # Column widths
        widths = [10, 20, 25, 16, 21, 25, 18, 20, 13, 20, 18]
        column_letters = [
            "A", "B", "C", "D", "E",
            "F", "G", "H", "I", "J", "K"
        ]

        for letter, width in zip(column_letters, widths):
            sheet.column_dimensions[letter].width = width

        sheet.freeze_panes = "A5"

        if customers:
            sheet.auto_filter.ref = (
                f"A4:K{header_row + len(customers)}"
            )

        # Save workbook in memory
        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        filename = "KYC_Branch_Wise_Report.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

    except Exception:
        app.logger.exception("Branch-wise Excel Export Error")
        flash("Unable to export the branch-wise report.", "danger")
        return redirect(url_for("branch_wise_report"))

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have logged out successfully.",
        "success"
    )

    return redirect(url_for("login"))

@app.route("/rekyc/schedule/<int:customer_id>", methods=["GET", "POST"])
def schedule_rekyc(customer_id):
    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        # Get customer details
        cursor.execute("""
            SELECT customer_id, customer_number, full_name,
                   account_number
            FROM customers
            WHERE customer_id = ?
        """, (customer_id,))

        customer = cursor.fetchone()

        if customer is None:
            flash("Customer not found.", "danger")
            return redirect(url_for("customers"))

        if request.method == "POST":
            scheduled_date = request.form.get("scheduled_date")
            remarks = request.form.get("remarks", "").strip()

            if not scheduled_date or scheduled_date < date.today().isoformat():
                flash("Please select a Re-KYC date.", "warning")
                return render_template(
                    "schedule_rekyc.html",
                    customer=customer, today_iso=date.today().isoformat()
                )

            existing_pending = conn.execute(
                "SELECT schedule_id FROM rekyc_schedule WHERE customer_id = ? AND LOWER(COALESCE(status, 'Pending')) = 'pending' LIMIT 1",
                (customer_id,)
            ).fetchone()
            if existing_pending:
                flash("This customer already has a pending re-KYC schedule. Edit the existing appointment instead.", "warning")
                return redirect(url_for("view_rekyc_schedules"))

            cursor.execute("""
                INSERT INTO rekyc_schedule
                (customer_id, scheduled_date, status, remarks)
                VALUES (?, ?, ?, ?)
            """, (
                customer_id,
                scheduled_date,
                "Pending",
                remarks
            ))

            conn.commit()

            flash("Re-KYC scheduled successfully!", "success")
            return redirect(url_for("customers"))

        return render_template(
            "schedule_rekyc.html",
            customer=customer, today_iso=date.today().isoformat()
        )

    except Exception:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Re-KYC Scheduling Error")
        flash("Unable to schedule Re-KYC. Check the terminal.", "danger")
        return redirect(url_for("customers"))

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()
@app.route("/rekyc/schedules")
def view_rekyc_schedules():

    # Check admin login
    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        cursor.execute("""
            SELECT
                rs.schedule_id,
                rs.customer_id,
                rs.scheduled_date,
                rs.status,
                rs.remarks,
                rs.created_at,
                c.full_name,
                c.customer_number,
                c.account_number
            FROM rekyc_schedule rs
            INNER JOIN customers c
                ON rs.customer_id = c.customer_id
            ORDER BY rs.scheduled_date DESC,
                     rs.schedule_id DESC
        """)

        schedules = cursor.fetchall()

        cursor.execute("""
            SELECT rs.schedule_id, rs.holder_id, rs.scheduled_date, rs.status,
                   rs.remarks, rs.created_at, jh.holder_name, jh.account_number
            FROM joint_rekyc_schedule rs JOIN joint_account_holders jh
              ON jh.holder_id = rs.holder_id
            ORDER BY rs.scheduled_date DESC, rs.schedule_id DESC
        """)
        joint_schedules = cursor.fetchall()
        return render_template(
            "rekyc_schedules.html",
            schedules=schedules,
            joint_schedules=joint_schedules
        )

    except Exception:
        app.logger.exception("Re-KYC Schedule List Error")
        flash("Unable to load Re-KYC schedules.", "danger")
        return redirect(url_for("customers"))

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()    
@app.route("/rekyc/schedules/complete/<int:schedule_id>", methods=["GET", "POST"])
def complete_rekyc_schedule(schedule_id):
    if "admin_id" not in session:
        return redirect(url_for("login"))
    connection = None
    try:
        connection = get_db_connection()
        schedule = connection.execute("""
            SELECT rs.schedule_id, rs.customer_id, rs.status, rs.scheduled_date,
                   c.full_name, c.customer_number, c.kyc_document,
                   c.kyc_issue_date, c.kyc_expiry_date
            FROM rekyc_schedule rs
            JOIN customers c ON c.customer_id = rs.customer_id
            WHERE rs.schedule_id = ?
        """, (schedule_id,)).fetchone()
        if not schedule:
            flash("Re-KYC schedule not found.", "warning")
            return redirect(url_for("view_rekyc_schedules"))
        if str(schedule["status"]).lower() == "completed":
            flash("This re-KYC schedule is already completed.", "info")
            return redirect(url_for("view_rekyc_schedules"))
        if request.method == "POST":
            document = request.form.get("kyc_document", "").strip()
            try:
                issue = parse_kyc_date(request.form.get("kyc_issue_date"))
                expiry = parse_kyc_date(request.form.get("kyc_expiry_date"))
            except ValueError:
                flash("Enter valid renewal issue and expiry dates.", "warning")
                return redirect(url_for("complete_rekyc_schedule", schedule_id=schedule_id))
            if not document or expiry <= issue or issue > date.today():
                flash("Select a document and a valid issue/expiry period. Issue date cannot be in the future.", "warning")
                return redirect(url_for("complete_rekyc_schedule", schedule_id=schedule_id))
            connection.execute("""
                UPDATE customers SET kyc_document = ?, kyc_issue_date = ?,
                kyc_expiry_date = ?, kyc_status = ? WHERE customer_id = ?
            """, (document, issue, expiry, kyc_status_for(expiry), schedule["customer_id"]))
            connection.execute("UPDATE rekyc_schedule SET status = 'Completed' WHERE schedule_id = ?", (schedule_id,))
            connection.commit()
            flash("Re-KYC completed and customer document dates updated.", "success")
            return redirect(url_for("view_rekyc_schedules"))
        return render_template("complete_rekyc.html", schedule=schedule)
    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Complete Re-KYC Error")
        flash("Unable to complete Re-KYC. Check the terminal.", "danger")
        return redirect(url_for("view_rekyc_schedules"))
    finally:
        if connection:
            connection.close()

@app.route("/rekyc/schedules/edit/<int:schedule_id>", methods=["GET", "POST"])
def edit_rekyc_schedule(schedule_id):

    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        # Update schedule
        if request.method == "POST":

            scheduled_date_value = request.form.get("scheduled_date", "").strip()
            status = request.form.get("status", "Pending").strip()
            remarks = request.form.get("remarks", "").strip()

            if not scheduled_date_value:
                flash("Please select a scheduled date.", "warning")

            elif status == "Completed":
                flash("Use Complete Re-KYC to enter renewed document details.", "warning")
                return redirect(url_for("complete_rekyc_schedule", schedule_id=schedule_id))

            elif status != "Pending":
                flash("Invalid schedule status.", "danger")

            else:
                scheduled_date = date.fromisoformat(scheduled_date_value)

                cursor.execute("""
                    UPDATE rekyc_schedule
                    SET scheduled_date = ?,
                        status = ?,
                        remarks = ?
                    WHERE schedule_id = ?
                """, (
                    scheduled_date,
                    status,
                    remarks,
                    schedule_id
                ))

                conn.commit()

                if cursor.rowcount == 0:
                    flash("No schedule was updated. Please check the schedule ID.", "warning")
                else:
                    flash("Re-KYC schedule updated successfully!", "success")

                return redirect(url_for("view_rekyc_schedules"))

        # Get existing schedule details
        cursor.execute("""
            SELECT
                rs.schedule_id,
                rs.customer_id,
                rs.scheduled_date,
                rs.status,
                rs.remarks,
                c.full_name,
                c.customer_number,
                c.account_number
            FROM rekyc_schedule AS rs
            INNER JOIN customers AS c
                ON rs.customer_id = c.customer_id
            WHERE rs.schedule_id = ?
        """, (schedule_id,))

        schedule = cursor.fetchone()

        if schedule is None:
            flash("Re-KYC schedule not found.", "warning")
            return redirect(url_for("view_rekyc_schedules"))

        return render_template(
            "edit_rekyc_schedule.html",
            schedule=schedule
        )

    except ValueError:
        if conn is not None:
            conn.rollback()

        flash("Please enter a valid scheduled date.", "warning")
        return redirect(
            url_for("edit_rekyc_schedule", schedule_id=schedule_id)
        )

    except Exception:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Edit Re-KYC Schedule Error")
        flash("Unable to edit Re-KYC schedule. Check the terminal for details.", "danger")
        return redirect(url_for("view_rekyc_schedules"))

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()

@app.route("/rekyc/schedules/delete/<int:schedule_id>", methods=["POST"])
def delete_rekyc_schedule(schedule_id):

    if "admin_id" not in session:
        return redirect(url_for("login"))

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = SQLiteCursor(conn)

        cursor.execute("""
            DELETE FROM rekyc_schedule
            WHERE schedule_id = ?
        """, (schedule_id,))

        if cursor.rowcount == 0:
            flash("Re-KYC schedule not found.", "warning")
        else:
            conn.commit()
            flash("Re-KYC schedule deleted successfully!", "success")

    except Exception:
        if conn is not None:
            conn.rollback()

        app.logger.exception("Delete Re-KYC Schedule Error")
        flash("Unable to delete Re-KYC schedule.", "danger")

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()

    return redirect(url_for("view_rekyc_schedules"))




     
# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------


# --------------------------------------------------
# JOINT-HOLDER RE-KYC: INDIVIDUAL SCHEDULE AND RENEWAL
# --------------------------------------------------
@app.route("/joint-holders/schedule/<int:holder_id>", methods=["GET", "POST"])
def schedule_joint_holder(holder_id):
    if "admin_id" not in session:
        return redirect(url_for("login"))
    connection = None
    try:
        connection = get_db_connection()
        holder = connection.execute("SELECT * FROM joint_account_holders WHERE holder_id = ?", (holder_id,)).fetchone()
        if holder is None:
            flash("Joint holder not found.", "warning")
            return redirect(url_for("joint_holders"))
        existing = connection.execute("""
            SELECT schedule_id, scheduled_date, remarks FROM joint_rekyc_schedule
            WHERE holder_id=? AND LOWER(COALESCE(status,'Pending'))='pending'
            ORDER BY schedule_id DESC LIMIT 1
        """, (holder_id,)).fetchone()
        if request.method == "POST":
            raw = request.form.get("scheduled_date", "")
            remarks = request.form.get("remarks", "").strip()
            try:
                scheduled = date.fromisoformat(raw)
            except ValueError:
                flash("Select a valid re-KYC date.", "warning")
                return redirect(url_for("schedule_joint_holder", holder_id=holder_id))
            if scheduled < date.today():
                flash("Please choose today or a future date.", "warning")
                return redirect(url_for("schedule_joint_holder", holder_id=holder_id))
            if existing:
                connection.execute(
                    "UPDATE joint_rekyc_schedule SET scheduled_date=?,remarks=? WHERE schedule_id=?",
                    (scheduled, remarks, existing["schedule_id"])
                )
                flash("Joint-holder appointment rescheduled.", "success")
            else:
                connection.execute("""
                    INSERT INTO joint_rekyc_schedule(holder_id, scheduled_date, status, remarks)
                    VALUES (?, ?, 'Pending', ?)
                """, (holder_id, scheduled, remarks))
                flash("Joint-holder re-KYC scheduled.", "success")
            connection.commit()
            return redirect(url_for("view_rekyc_schedules"))
        return render_template("schedule_joint_holder.html", holder=holder,
                               schedule=existing, today_iso=date.today().isoformat())
    except Exception:
        if connection: connection.rollback()
        app.logger.exception("Joint-holder scheduling failed")
        flash("Unable to schedule joint-holder re-KYC.", "danger")
        return redirect(url_for("joint_holders"))
    finally:
        if connection: connection.close()


@app.route("/joint-holders/schedules/complete/<int:schedule_id>", methods=["GET", "POST"])
def complete_joint_holder_rekyc(schedule_id):
    if "admin_id" not in session:
        return redirect(url_for("login"))
    connection = None
    try:
        connection = get_db_connection()
        record = connection.execute("""
            SELECT rs.schedule_id, rs.holder_id, rs.status,
                   jh.holder_name, jh.account_number, jh.kyc_document
            FROM joint_rekyc_schedule rs
            JOIN joint_account_holders jh ON jh.holder_id = rs.holder_id
            WHERE rs.schedule_id = ?
        """, (schedule_id,)).fetchone()
        if record is None:
            flash("Joint-holder appointment not found.", "warning")
            return redirect(url_for("view_rekyc_schedules"))
        if str(record["status"]).lower() == "completed":
            flash("This appointment is already completed.", "info")
            return redirect(url_for("view_rekyc_schedules"))
        if request.method == "POST":
            doc = request.form.get("kyc_document", "").strip()
            try:
                issue = parse_kyc_date(request.form.get("kyc_issue_date"))
                expiry = parse_kyc_date(request.form.get("kyc_expiry_date"))
            except ValueError:
                flash("Enter valid renewed document dates.", "warning")
                return redirect(url_for("complete_joint_holder_rekyc", schedule_id=schedule_id))
            if not doc or issue > date.today() or expiry <= issue:
                flash("Provide a document with a valid issue/expiry period.", "warning")
                return redirect(url_for("complete_joint_holder_rekyc", schedule_id=schedule_id))
            connection.execute("""
                UPDATE joint_account_holders
                SET kyc_document=?, kyc_issue_date=?, kyc_expiry_date=?, kyc_status=?
                WHERE holder_id=?
            """, (doc, issue, expiry, kyc_status_for(expiry), record["holder_id"]))
            connection.execute("UPDATE joint_rekyc_schedule SET status='Completed' WHERE schedule_id=?", (schedule_id,))
            connection.commit()
            flash("Joint-holder re-KYC completed and document renewed.", "success")
            return redirect(url_for("view_rekyc_schedules"))
        return render_template("complete_rekyc.html", schedule=record, holder_mode=True)
    except Exception:
        if connection: connection.rollback()
        app.logger.exception("Joint holder completion failed")
        flash("Unable to complete joint-holder re-KYC.", "danger")
        return redirect(url_for("view_rekyc_schedules"))
    finally:
        if connection: connection.close()


@app.route("/joint-holders/schedules/delete/<int:schedule_id>", methods=["POST"])
def delete_joint_holder_schedule(schedule_id):
    if "admin_id" not in session:
        return redirect(url_for("login"))
    connection = None
    try:
        connection = get_db_connection()
        connection.execute("DELETE FROM joint_rekyc_schedule WHERE schedule_id=?", (schedule_id,))
        connection.commit()
        flash("Joint-holder appointment removed.", "success")
    except Exception:
        if connection:connection.rollback()
        app.logger.exception("Joint holder schedule deletion failed")
        flash("Unable to delete joint-holder appointment.", "danger")
    finally:
        if connection:connection.close()
    return redirect(url_for("view_rekyc_schedules"))

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true"
    )
