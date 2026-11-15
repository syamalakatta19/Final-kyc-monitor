# KYC Monitor – SQLite backend migration

This distribution uses SQLite instead of MySQL. Your uploaded `kyc_monitor.db` is retained without modification, including the existing administrator record.

## Setup on Windows

1. Install Python dependencies from the project folder: `python -m pip install -r requirements.txt`.
2. Copy `.env.example` to `.env` in the `KYC_Monitor_New` root.
3. Generate your own Flask session key: `python -c "import secrets; print(secrets.token_hex(32))"` and paste its value into `FLASK_SECRET_KEY` in `.env`.
4. Run `cd backend` then `python app.py`.
5. Log in with the admin account you created before this migration.

The existing admin password cannot be read from its hash. Use `python secure_admin.py` to set a new password for an existing account if necessary. Do not include `.env` in shared ZIP files.

## Migration summary

- `backend/app.py`: SQLite-compatible query parameters, date functions, and cursor row types. Debug disabled by default; local host binding; HTTP-only / SameSite session cookie settings.
- `backend/secure_admin.py`: SQLite placeholders and username-targeted password updates.
- `backend/database.py`, `backend/init_database.py`, and `kyc_monitor.db`: unchanged.
- `frontend/`: unchanged.
- `.env.example`, `.gitignore` and `requirements.txt`: for safe setup and sharing.

## Validation and caveats

Static Python syntax and SQLite SQL preparation tests passed. Dashboard SQL was executed on a temporary copy with synthetic data. Full browser-level Flask testing must be performed locally because Flask, python-dotenv and openpyxl are not installed in the packaging environment.

The database currently contains an administrator password hash. Treat the included database as a development file, not a public demo distribution, until you've generated an isolated demo admin account and removed any sensitive records. SQLite does not encrypt database contents by default. The three-format date-of-birth import requirement is not yet implemented.

## Forgot password (local SQLite demo)

The login now includes **Forgot password?**. Because this project's admin records have no verified email addresses, recovery codes are issued **on the computer holding the SQLite database**, never automatically through a public web request.

1. From `backend`, run `python issue_reset_code.py`.
2. Enter the existing admin username. The script displays a high-entropy code that expires in 15 minutes; it stores only its SHA-256 hash.
3. Open `http://127.0.0.1:5000/forgot-password`, enter username, code, and a new password (12+ characters).
4. After successful reset, the recovery code is deleted and the admin can sign in with the new password.

If you are deploying this to a remote server, use an authenticated administrator-managed or verified-email recovery mechanism instead of giving users server-terminal access. Protect the `.db` file from public download and sharing.
