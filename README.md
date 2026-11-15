# KYC Document Expiry Monitor for Bank Branches

A web-based **banking compliance management prototype** that helps branch administrators monitor customer identity-document expiry, schedule and complete re-KYC, and review branch-wise pending work. Built with **Python, Flask, SQLite, HTML, CSS, JavaScript, Bootstrap, and Chart.js**.

> **Project scope:** Educational/college demonstration. This application is not certified for use with real banking customer data or production compliance operations.

## Problem Statement

Bank branches must periodically review customer KYC (Know Your Customer) documents and follow up when identity proofs are nearing expiration. The project addresses two principal use cases:

1. **Scan customer records for expiring ID proofs and schedule re-KYC.**
2. **Produce a branch-wise report of pending re-KYC work.**

It also addresses two data-handling challenges: customer dates of birth supplied in different text formats, and joint account holders who share an account but have **independent KYC dates**.

## Features

- **Administrator access:** Hashed-password login, logout, session management, and a local recovery-code flow for forgotten passwords.
- **Dashboard:** Customer/KYC summary counts, expiry alerts, monthly expiry chart, and branch-level overview.
- **Customer management:** Add, view, edit, search, and delete customer records; store account and KYC document details.
- **Branch management:** Register and maintain bank branches; associate customers with branches.
- **Joint account holders:** Maintain separate KYC documents, issue dates, and expiry dates for holders linked to an existing customer account.
- **Expiry monitoring:** Classify documents as **Valid**, **Expiring Soon** (within 30 days), **Expired**, or unavailable/unknown when required information is missing.
- **Re-KYC scheduling:** Schedule or reschedule customer and joint-holder appointments, track statuses and remarks, and record renewed document details when completing re-KYC.
- **Reports:** Monthly KYC expiry views, branch-wise summaries including pending re-KYC, filters, and **Excel (.xlsx) exports**.
- **DOB normalization:** Accept `YYYY-MM-DD`, `DD-MM-YYYY`, and `MM/DD/YYYY` and normalize newly entered dates.
- **Shared interface:** Consistent navigation across authenticated pages, responsive tables, and a minimal banking-themed UI.

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| Database | SQLite3 (Python standard library) |
| Frontend | HTML5, CSS3, JavaScript |
| UI | Bootstrap 5, Bootstrap Icons |
| Charts | Chart.js |
| Excel exports | openpyxl |
| Configuration | python-dotenv |
| Authentication | Werkzeug password hashing, Flask sessions |

## Project Structure

```text
KYC_Monitor_New/
├── backend/
│   ├── app.py                     # Flask routes and application logic
│   ├── database.py                # SQLite connection
│   ├── init_database.py           # Create database tables
│   ├── create_admin.py            # Create administrator account
│   ├── secure_admin.py            # Admin password maintenance utility
│   ├── issue_reset_code.py        # Local password recovery code
│   └── seed_demo_data.py          # Optional synthetic demo records
├── frontend/
│   ├── templates/                 # Login, dashboard, management and report pages
│   │   └── _navigation.html       # Shared navigation
│   └── static/
│       ├── css/style.css          # Shared theme and visual effects
│       └── js/                    # Dashboard chart and UI scripts
├── tests/
│   └── test_workflows.py          # Automated workflow tests
├── requirements.txt
└── README.md
```

The application stores its local SQLite database at `KYC_Monitor_New/kyc_monitor.db`. **Do not commit a private or real-data database file to a public repository.**

## Getting Started

### Prerequisites

- Python **3.10 or later** (a supported release recommended)
- `pip`
- A modern web browser

**MySQL is not required.** SQLite is built into Python.

### 1. Download and open the project

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

> Replace `YOUR_USERNAME/YOUR_REPOSITORY` with the actual GitHub repository URL. If the repository contains the `KYC_Monitor_New` folder rather than its contents, run `cd KYC_Monitor_New` as well.

### 2. Create a virtual environment

**Windows (Command Prompt):**

```cmd
python -m venv .venv
.venv\Scripts\activate
```

**macOS/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure the Flask secret key

Create a file named **`.env` in the project root**, beside `requirements.txt`:

```dotenv
FLASK_SECRET_KEY=REPLACE_WITH_A_RANDOM_SECRET_KEY
FLASK_DEBUG=false
FLASK_HTTPS=false
```

Generate a key locally:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the generated value in `.env`. Keep that file private. `FLASK_HTTPS=false` is for local HTTP development; deploy only behind properly configured HTTPS and enable secure cookies in production.

### 5. Initialize SQLite and create an admin

For a fresh installation:

```bash
python backend/init_database.py
python backend/create_admin.py
```

Follow the terminal prompts to select an administrator username and strong password (12 or more characters).

**Existing users:** If you have a database containing your records, back it up before replacing or reinitializing anything. `init_database.py` creates missing tables; it does not import data from another computer's database.

### 6. Start the website

```bash
python backend/app.py
```

Open **http://127.0.0.1:5000** in your browser and sign in with the administrator account you created.

### 7. Optional: Add fictional demo records

After initializing an **empty business database**, you may run:

```bash
python backend/seed_demo_data.py
```

This inserts synthetic branches, customers, joint holders, and an appointment for demonstration. The script refuses to insert demo data if the relevant business tables already contain records; it does not alter administrator credentials.

## How to Use

1. **Create branches** in *Branch Management*.
2. **Add customers** and enter their account, identity-document, issue-date, and expiry-date details.
3. **Add joint holders** to an existing account, recording KYC details separately for each individual.
4. **Review the dashboard** for upcoming or expired documents.
5. **Schedule re-KYC** through the customer or joint-holder actions.
6. **Complete re-KYC** by recording the renewed identity document and valid issue/expiry dates.
7. **Review branch-wise and monthly reports** and export Excel files where needed.

## Forgot Password (Local Demo)

This version does **not** send a password reset email. Recovery requires authorized local access to the server/database host:

```bash
python backend/issue_reset_code.py
```

Enter the admin username to generate a **single-use code valid for 15 minutes**. Visit `/forgot-password` on the running website and submit the username, code, and new password. Do not share the code.

## Testing

From the project root:

```bash
python -m unittest discover -s tests -v
```

The repository includes automated tests for core workflows. You should also manually verify login, customer search, document expiry status, scheduling, renewals, and both report pages in the browser.

## Screenshots

Screenshots are not bundled in this README. To display them on GitHub, add sanitized images to a `screenshots/` directory and uncomment/update the links below:

```markdown
<!-- ![Dashboard](screenshots/dashboard.png) -->
<!-- ![Customer Management](screenshots/customers.png) -->
<!-- ![Re-KYC Schedules](screenshots/rekyc-schedules.png) -->
<!-- ![Branch-wise Report](screenshots/branch-report.png) -->
```

Use fictional records in screenshots; avoid real names, account numbers, and identity-document information.

## Security and Privacy

**Before pushing to a public GitHub repository:**

- **Do not upload `.env`.** It contains the Flask session secret.
- **Do not upload `kyc_monitor.db`** if it contains an admin account, customer information, or other private data. The supplied project ZIP includes these files; remove them from the GitHub copy.
- Do not upload real KYC documents, customer records, password-reset codes, or credentials.
- Ignore `.venv/`, `__pycache__/`, `*.pyc`, and local log files.
- Generate a new secret key for each deployment. Use a separate demo database for screenshots and demonstrations.
- A classroom Flask application needs additional security, access control, privacy, auditing, backup, and deployment review before real-world banking use.

Suggested root `.gitignore`:

```gitignore
.env
.env.*
!.env.example
.venv/
venv/
__pycache__/
*.pyc
*.log
kyc_monitor.db
*.db-wal
*.db-shm
```

> `.gitignore` does not remove files already committed to Git history. If a credential or private database was previously committed, remove it from tracking/history as appropriate and rotate exposed secrets.

## Known Limitations and Future Improvements

- Local SQLite is convenient for demonstrations; deployment with multiple concurrent staff members would require additional architecture and operational planning.
- Password recovery is terminal-assisted, not verified-email based.
- Historical versions of renewed KYC documents are not retained as a dedicated audit trail.
- Automated SMS/email reminders, stronger role-based permissions, comprehensive audit logs, and production-grade security are not included.
- All workflows should be validated with test records and suitable security/privacy procedures before use beyond a college demonstration.

## License

No license is specified in the supplied project. Add a `LICENSE` file if the project owners decide to publish it under an open-source license.
