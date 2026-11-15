"""Basic end-to-end workflow tests using a temporary SQLite database.

From KYC_Monitor_New run: python -m unittest discover -s tests -v
Tests never modify kyc_monitor.db or any real user data.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("FLASK_SECRET_KEY", "testing-key-is-not-for-real-deployments")

import database
import init_database
import app as project


class KYCWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kyc_workflow_test_")
        self.previous_path = database.DATABASE_PATH
        database.DATABASE_PATH = Path(self.temp.name) / "test.db"
        init_database.initialize_database()
        project.app.config["TESTING"] = True
        project.app.config["JOINT_REKYC_SCHEMA_READY"] = False
        self.client = project.app.test_client()
        conn = database.get_db_connection()
        conn.execute("INSERT INTO admins(username,password) VALUES('testadmin','test-only-hash')")
        conn.execute("INSERT INTO branches(branch_code,branch_name,city) VALUES('DEMO','Test Branch','Test City')")
        conn.execute("""INSERT INTO customers
            (customer_number,full_name,dob,phone,branch_id,account_type,account_number,kyc_document,kyc_issue_date,kyc_expiry_date)
            VALUES('DEMO-1','Test Customer','2000-01-02','9000000000',1,'Savings','TEST-ACCT','Passport','2025-01-01','2026-01-01')""")
        conn.execute("""INSERT INTO joint_account_holders
            (account_number,holder_name,dob,phone,kyc_document,kyc_issue_date,kyc_expiry_date)
            VALUES('TEST-ACCT','Test Holder','2001-02-03','9000000001','Passport','2025-01-01','2026-01-02')""")
        conn.commit()
        conn.close()
        with self.client.session_transaction() as session:
            session['admin_id'] = 1
            session['admin_username'] = 'testadmin'
            session['_csrf_token'] = 'testing-csrf-value'

    def tearDown(self):
        database.DATABASE_PATH = self.previous_path
        self.temp.cleanup()

    def test_three_dob_formats(self):
        parse = project.parse_kyc_date
        self.assertEqual(parse('2000-08-15'), parse('15-08-2000'))
        self.assertEqual(parse('15-08-2000'), parse('08/15/2000'))
        with self.assertRaises(ValueError):
            parse('31/02/2000')

    def test_search_and_dashboard(self):
        self.assertIn(b'Test Customer', self.client.get('/customers?q=Test%20Customer').data)
        self.assertNotIn(b'Test Customer', self.client.get('/customers?q=NotFoundValue').data)
        page = self.client.get('/dashboard')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Test Holder', page.data)

    def test_csrf_required(self):
        response = self.client.post('/rekyc/schedule/1', data={'scheduled_date': '2030-01-01'})
        self.assertEqual(response.status_code, 400)

    def test_customer_renewal_prevents_duplicate_schedules(self):
        url = '/rekyc/schedule/1'
        data = {'scheduled_date': '2030-01-01', '_csrf_token': 'testing-csrf-value'}
        self.assertEqual(self.client.post(url, data=data).status_code, 302)
        self.assertEqual(self.client.post(url, data=data).status_code, 302)
        conn = database.get_db_connection()
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM rekyc_schedule').fetchone()[0], 1)
        conn.close()
        response = self.client.post('/rekyc/schedules/complete/1', data={
            '_csrf_token':'testing-csrf-value', 'kyc_document':'Passport',
            'kyc_issue_date':'2025-01-01','kyc_expiry_date':'2031-01-01'
        })
        self.assertEqual(response.status_code, 302)
        conn = database.get_db_connection()
        self.assertEqual(conn.execute('SELECT kyc_expiry_date FROM customers').fetchone()[0], '2031-01-01')
        self.assertEqual(conn.execute('SELECT status FROM rekyc_schedule').fetchone()[0], 'Completed')
        conn.close()

    def test_joint_holder_independent_renewal(self):
        self.assertEqual(self.client.post('/joint-holders/schedule/1', data={
            '_csrf_token':'testing-csrf-value', 'scheduled_date':'2030-01-01', 'remarks':'Test'
        }).status_code, 302)
        branch_report = self.client.get('/reports/branch-wise')
        self.assertEqual(branch_report.status_code, 200)
        self.assertIn(b'Pending Appointments', branch_report.data)
        self.assertEqual(self.client.post('/joint-holders/schedules/complete/1', data={
            '_csrf_token':'testing-csrf-value','kyc_document':'Passport',
            'kyc_issue_date':'2026-01-01','kyc_expiry_date':'2031-01-01'
        }).status_code, 302)
        conn = database.get_db_connection()
        self.assertEqual(conn.execute('SELECT kyc_expiry_date FROM joint_account_holders').fetchone()[0], '2031-01-01')
        self.assertEqual(conn.execute('SELECT kyc_expiry_date FROM customers').fetchone()[0], '2026-01-01')
        conn.close()

    def test_branch_excel_export(self):
        response = self.client.get('/reports/branch-wise/export')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.startswith(b'PK'))


if __name__ == '__main__':
    unittest.main()
