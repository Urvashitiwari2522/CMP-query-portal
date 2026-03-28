College Query Management Portal - Backend

Overview
- Flask-based backend API for handling query submission and admin management.
- SQLite database (easily switchable to MySQL).
- Session-based admin authentication, CORS, and email notifications.

Requirements
- Python 3.10+
- pip

Setup
1. Clone or open this repository.
2. Create and activate a virtual environment (recommended).
3. Install dependencies:
   pip install -r backend/requirements.txt
4. Create a .env file in backend/ (optional; otherwise defaults are used):
   cp backend/.env.example backend/.env  # on Windows, copy the file manually
5. Initialize the database and default admin:
   python -m backend.init_db
6. Run the server:
   python -m backend.app

Environment Variables (.env)
- SECRET_KEY=your-secret-key-here
- DATABASE_URI=sqlite:///college_qmp.db
- CORS_ORIGINS=http://localhost:3000
- MAIL_SERVER=smtp.gmail.com
- MAIL_PORT=587
- MAIL_USERNAME=your-email@gmail.com
- MAIL_PASSWORD=your-app-password
- MAIL_USE_TLS=True

API Endpoints
Public
- POST /api/submit-query
  Body JSON: { name, email, phone, query_type, message }
- GET /api/query-status/<id>

Admin (session required)
- POST /api/admin/login  Body: { username, password }
- POST /api/admin/logout
- GET /api/admin/check-auth
- GET /api/admin/queries?status=&query_type=&search=&page=1&limit=10
- GET /api/admin/queries/<id>
- PUT /api/admin/queries/<id>  Body: { status, admin_response }
- DELETE /api/admin/queries/<id>
- GET /api/admin/stats

Curl Examples
- Submit Query:
  curl -X POST http://localhost:5000/api/submit-query \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"John Doe\",\"email\":\"john@example.com\",\"phone\":\"1234567890\",\"query_type\":\"admissions\",\"message\":\"Need help with admission process\"}"

- Admin Login (store cookies for session):
  curl -i -c cookies.txt -X POST http://localhost:5000/api/admin/login \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"admin\",\"password\":\"admin123\"}"

- List Queries:
  curl -b cookies.txt "http://localhost:5000/api/admin/queries?page=1&limit=10"

- Update Query:
  curl -b cookies.txt -X PUT http://localhost:5000/api/admin/queries/1 \
    -H "Content-Type: application/json" \
    -d "{\"status\":\"resolved\",\"admin_response\":\"Issue resolved.\"}"

- Logout:
  curl -b cookies.txt -X POST http://localhost:5000/api/admin/logout

Testing Data
- After init_db, default admin is created (admin/admin123).

Implementation Notes
- Uses sqlite3 with parameterized queries to prevent SQL injection.
- Passwords are hashed using Werkzeug.
- CORS is configured for /api/* routes with credentials support.
- Email sending will log and skip if MAIL_USERNAME is not configured.
