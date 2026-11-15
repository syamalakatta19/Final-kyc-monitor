# KYC requirements review — applied updates

- Removed redundant breadcrumb hierarchy and duplicate Back-to-Dashboard links (shared sidebar remains).
- Customer directory now performs parameterized customer / account / document searches.
- DOB accepts three *unambiguous configured* formats: ISO `YYYY-MM-DD`, day-first `DD-MM-YYYY`, and month-first `MM/DD/YYYY`. Stored values remain ISO.
- Joint-holder creation/edit checks that the account exists in customer records. Each holder retains independent issue and expiry dates. Account-number edits on last owning customer update matching holders. Deleting the only customer for an account containing holders is prevented.
- Dashboard expiry alerts include individual joint holders, with links to their directory.
- Re-KYC scheduling prevents a second pending appointment for the same customer.
- Completing re-KYC now requires renewed document details and updates the customer record in the same SQLite transaction as completing the appointment.
- Branch-wise reports include pending counts by branch and per-customer pending indicators; Excel export has the same extra column.
- All HTML POST forms have session-based CSRF validation; Flask session cookie flags set. Password-recovery form retains its separate recovery-form token.
- Existing SQLite database and admin account left unchanged. No demo customer data added to the existing database.

## Remaining limitations
- Joint holders now have independent schedules and renewal recording in the new `joint_rekyc_schedule` table; these are shown on the existing Re-KYC Schedules page. The new table is created automatically on first request and is included in `init_database.py`.
- The customer edit form records renewed dates but does not retain a historical version of old documents.
- The original application has many independent routes and legacy styles; browser-level regression tests are required before production usage.
- This is a classroom prototype, not a production-grade bank compliance platform. Real financial/customer identity data should not be loaded without a full security and privacy review.

## Optional demonstration data

Run `python backend/seed_demo_data.py` from the project root after `init_database.py` if you want synthetic data for a college demonstration. It refuses to insert any demo data into an already populated business database. It does not change the admin account. The ZIP deliberately preserves your current SQLite database without adding demo records.
