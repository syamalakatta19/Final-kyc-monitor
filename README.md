# 🏦 KYC Document Expiry Monitoring System

### Smart Banking Compliance & Customer KYC Management

A web-based **KYC Document Expiry Monitoring System** developed using Python Flask and MySQL to help bank branches manage customer KYC records, monitor document expiry dates, schedule re-KYC activities, and generate compliance reports.

The system provides a centralized dashboard with a consistent, professional user interface to simplify banking compliance management.

---

## 📌 Project Overview

Banks need to maintain updated Know Your Customer (KYC) documents for their customers. Manually tracking document expiry dates can lead to delays, outdated records, and compliance issues.

This project provides a digital solution that helps bank administrators manage customer information, monitor KYC expiry status, and organize re-KYC schedules efficiently.

## ✨ Key Features

- **Admin Login:** Secure administrator authentication.
- **Dashboard:** Displays total customers, valid KYC, expiring KYC, expired KYC, and pending re-KYC schedules.
- **Customer Management:** Add, view, edit, and delete customer records.
- **KYC Expiry Monitoring:** Automatically identifies documents as Valid, Expiring Soon, or Expired.
- **Branch Management:** Manage bank branches and their information.
- **Joint Account Management:** Maintain information about joint account holders.
- **Re-KYC Scheduling:** Schedule, update, and track customer re-KYC activities.
- **Monthly KYC Reports:** Generate monthly KYC expiry reports.
- **Branch-Wise Reports:** Monitor KYC information branch by branch.
- **Excel Export:** Export monthly and branch-wise reports into Excel files.
- **Notifications:** View KYC expiry notifications through the dashboard.
- **Consistent UI:** Standardized navigation, sidebar, dashboard, and page styling.

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| Flask | Web application framework |
| MySQL | Database management |
| HTML5 | Frontend structure |
| CSS3 | Styling and responsive design |
| JavaScript | Frontend interactions |
| Bootstrap | UI components |
| Chart.js | Dashboard visualizations |
| OpenPyXL | Excel report generation |
| Werkzeug | Password hashing |
| VS Code | Development environment |


⚙️ Installation and Setup

1. Clone the Repository

git clone https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git

2. Open the Project

cd KYC_Monitor_New

3. Create a Virtual Environment

python -m venv .venv

Activate it on Windows:

.venv\Scripts\activate

4. Install Dependencies

pip install -r requirements.txt

5. Configure MySQL Database

Install and open MySQL Workbench.

Create or restore the required kyc_monitor database.

Ensure the required tables are available.

Note: The repository does not include a database SQL dump. You must prepare the database separately.

6. Configure Environment Variables

Create a .env file in the project root using .env.example.

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=kyc_monitor

FLASK_SECRET_KEY=your_secret_key

Replace the sample values with your local database credentials and a strong secret key.

7. Run the Application

Open the backend folder:

cd backend

Start the Flask application:

python app.py

8. Open in Browser

http://127.0.0.1:5000

Log in using an administrator account configured in your database.

📊 KYC Expiry Status Logic

The system automatically determines KYC document status based on the expiry date.

Status

Condition

Valid

Expiry date is more than 30 days away

Expiring Soon

Expiry date is within the next 30 days

Expired

Expiry date has already passed

🎯 Project Objectives

Reduce manual KYC tracking.

Improve customer document management.

Identify expired and expiring KYC documents.

Simplify re-KYC scheduling.

Improve branch-wise compliance monitoring.

Generate organized banking compliance reports.

🚀 Future Enhancements

SMS and email notifications for KYC expiry reminders.

AI-based KYC document verification.

Customer self-service portal.

Advanced analytics and compliance predictions.

Cloud deployment and real-time monitoring.

🔒 Security Notes

Admin passwords are stored using secure password hashing.

Database credentials are configured through environment variables.

Do not upload your actual .env file or sensitive database credentials to GitHub.

Use HTTPS and a production WSGI server before deployment.

👩‍💻 Developed By

Syamala Katta

Project: KYC Document Expiry Monitoring System

Domain: Banking Compliance Management

Technologies: Python | Flask | MySQL | HTML | CSS | JavaScript | Bootstrap

⭐ If you find this project useful, consider giving this repository a star!

Thank you for visiting my project!
