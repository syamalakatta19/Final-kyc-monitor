"""Optional synthetic demonstration data for an EMPTY KYC database.

Run: python seed_demo_data.py
The script refuses to run if any real branch, customer, joint-holder or
re-KYC records exist. It never modifies administrator credentials.
"""
from datetime import date, timedelta
from database import get_db_connection


def iso(days):
    return (date.today() + timedelta(days=days)).isoformat()


def status(days):
    if days < 0:
        return "Expired"
    if days <= 30:
        return "Expiring Soon"
    return "Valid"


def main():
    connection = get_db_connection()
    try:
        for table in ("branches", "customers", "joint_account_holders", "rekyc_schedule", "joint_rekyc_schedule"):
            # A new DB may not have the optional joint schedule table until first run.
            try:
                count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception:
                if table == "joint_rekyc_schedule":
                    continue
                raise
            if count:
                print(f"No changes made: {table} already has records.")
                return

        branches = [
            ("DEMO-B01", "Central Branch", "Hyderabad"),
            ("DEMO-B02", "East Branch", "Vijayawada"),
            ("DEMO-B03", "South Branch", "Tirupati"),
        ]
        connection.executemany("INSERT INTO branches(branch_code,branch_name,city) VALUES (?,?,?)", branches)
        ids = [row[0] for row in connection.execute("SELECT branch_id FROM branches ORDER BY branch_id")]
        people = [
            ("DEMO-001", "Asha Kumar", "1994-05-10", "9000000001", ids[0], "DEMO-ACC01", -17),
            ("DEMO-002", "Ravi Das", "1988-03-12", "9000000002", ids[0], "DEMO-ACC02", 12),
            ("DEMO-003", "Meera Shah", "1996-09-19", "9000000003", ids[1], "DEMO-ACC03", 70),
            ("DEMO-004", "Kiran Rao", "1981-11-02", "9000000004", ids[1], "DEMO-ACC04", -5),
            ("DEMO-005", "Priya Nair", "1992-12-28", "9000000005", ids[2], "DEMO-ACC05", 23),
            ("DEMO-006", "Arjun Patel", "1999-01-08", "9000000006", ids[2], "DEMO-ACC06", 120),
        ]
        connection.executemany("""
          INSERT INTO customers(customer_number,full_name,dob,phone,branch_id,
            account_type,account_number,kyc_document,kyc_issue_date,kyc_expiry_date,kyc_status)
          VALUES (?,?,?,?,?,'Savings',?,'Passport',?,?,?)
        """, [(number,name,dob,phone,branch,account,iso(-365),iso(days),status(days))
              for number,name,dob,phone,branch,account,days in people])
        customer_ids = {r["customer_number"]:r["customer_id"] for r in connection.execute("SELECT customer_id, customer_number FROM customers")}
        connection.executemany("""
          INSERT INTO joint_account_holders(account_number,holder_name,dob,phone,
            kyc_document,kyc_issue_date,kyc_expiry_date,kyc_status)
          VALUES (?,?,?,?,?,?,?,?)
        """, [
            ("DEMO-ACC01", "Sana Kumar", "1996-07-15", "9000000007", "Passport", iso(-365), iso(18), "Expiring Soon"),
            ("DEMO-ACC03", "Nikhil Shah", "1995-09-20", "9000000008", "Passport", iso(-365), iso(-10), "Expired"),
        ])
        connection.execute("""INSERT INTO rekyc_schedule(customer_id,scheduled_date,status,remarks)
                              VALUES (?,?,'Pending','Synthetic demo appointment')""",
                           (customer_ids["DEMO-001"],iso(7)))
        connection.commit()
        print("Synthetic demo data added: 3 branches, 6 customers, 2 joint holders, 1 appointment.")
        print("Admin account and password were not changed.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
