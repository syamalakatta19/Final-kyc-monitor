# KYC Monitor — requirements-aligned update

## Run the project

1. Install Python 3.10+ and run `python -m pip install -r requirements.txt` in the project root.
2. Copy `.env.example` to `.env` and replace the placeholder `FLASK_SECRET_KEY` with a random secret (`python -c "import secrets; print(secrets.token_hex(32))"`). Never commit `.env`.
3. Keep the existing `kyc_monitor.db` if you want to retain your admin account. **Back it up before replacing any project version.**
4. Run `python backend/init_database.py` once to create missing tables, including joint-holder schedules. The app can also add the new joint schedule table automatically on first request.
5. Start the website with `python backend/app.py`. Open `http://127.0.0.1:5000`.
6. To run automated tests without modifying your real database: `python -m unittest discover -s tests -v`.
7. Optional, for an **empty database only**, run `python backend/seed_demo_data.py` to add fictional demonstration customers, branches, joint holders, and an appointment. The script refuses to run when these tables already contain records.

## Important workflows

- Customer directory search now searches name, customer number, account number, and KYC document.
- Customer and joint-holder DOB values accept **YYYY-MM-DD**, **DD-MM-YYYY**, or **MM/DD/YYYY**; new values are saved in ISO form.
- A joint-holder account number must match an existing customer account. Each holder has its own KYC expiry dates and can schedule and complete a separate re-KYC appointment.
- A second pending re-KYC appointment for the same customer is prevented; joint-holder appointments can be rescheduled.
- To complete re-KYC, the administrator must enter a new document and valid issue/expiry dates; closing the appointment updates the associated KYC record.
- Branch-wise reports include pending re-KYC appointments, show branch-level totals, support **Pending Re-KYC Only**, and export that status to Excel.
- Every POST form has CSRF protection. Forgot Password still requires a one-time locally issued reset code.
- Repeated breadcrumb trails and some redundant Back to Dashboard links were removed; the same sidebar remains.

## Notes

- Existing `.db` data was preserved in the release. This includes an administrator password hash; keep the ZIP private.
- Do not upload real banking KYC records to a public demo repository.
- The website is a classroom prototype, not a production banking platform. It needs a formal security/privacy review, backup/recovery strategy, audit logs, and browser testing before any real deployment.
- No automatic external notifications (SMS/email) were added; the application provides in-app monitoring and manual scheduling.
