import os
import sys
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mail import Mail, Message
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
import re
import csv
from models import db, Query, Admin, Student
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///cmp_queries.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret-change')

# Mail configuration (use environment variables in production)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() in ('1', 'true', 'yes')
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'False').lower() in ('1', 'true', 'yes')
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config.get('MAIL_USERNAME'))

# Safe reset: delete DB file only when RESET_DB=1 is set in environment.
# This prevents accidental destructive deletes. To reset, run once with:
# PowerShell: $env:RESET_DB='1'; python app.py
if os.environ.get('RESET_DB') == '1':
    db_file = 'cmp_queries.db'
    try:
        if os.path.exists(db_file):
            os.remove(db_file)
            print('OLD DATABASE DELETED - Fresh start')
    except Exception as e:
        print('Failed to delete old database:', e)

# initialize db
db.init_app(app)

# Initialize Flask-Mail
mail = Mail(app)
# Log SMTP configuration for diagnostics (non-breaking)
try:
    print(f"SMTP Config: {app.config.get('MAIL_USERNAME')} | Port: {app.config.get('MAIL_PORT')}")
except Exception:
    pass


def create_tables():
    """Create DB tables and a default admin if missing.

    Note: some environments may not expose app.before_first_request; calling
    this function manually within an app_context() at startup is more robust.
    """
    # Ensure tables exist
    db.create_all()

    # Detect if the `student_id` column exists in the `queries` table and add it
    # if missing. This helps deployments that already have an existing SQLite
    # database created before adding the column to the model.
    try:
        # Use a direct engine connection; PRAGMA table_info returns rows where
        # the column name is at index 1. This is more robust than relying on
        # row keys which can vary depending on the DBAPI.
        conn = db.engine.connect()
        result = conn.execute(text("PRAGMA table_info('queries')"))
        rows = result.fetchall()
        cols = [r[1] for r in rows] if rows else []
        if 'student_id' not in cols:
            app.logger.info('Adding student_id column to queries table')
            # store numeric FK to students.id
            conn.execute(text("ALTER TABLE queries ADD COLUMN student_id INTEGER"))
            # ensure the DDL is persisted
            db.session.commit()
        # Ensure optional columns exist for compatibility (idempotent)
        try:
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info('queries')")).fetchall()] or []
            if 'category' not in cols:
                app.logger.info('Adding category column to queries table')
                conn.execute(text("ALTER TABLE queries ADD COLUMN category TEXT"))
                db.session.commit()
            if 'admin_response' not in cols:
                app.logger.info('Adding admin_response column to queries table')
                conn.execute(text("ALTER TABLE queries ADD COLUMN admin_response TEXT"))
                db.session.commit()
        except Exception:
            app.logger.exception('Error ensuring optional query columns exist')
        conn.close()
    except Exception as exc:
        app.logger.exception('Error ensuring student_id column exists: %s', exc)
        try:
            db.session.rollback()
        except Exception:
            pass

    # create default admin if none exists (username: cmpquery@gmail.com, password: Admin@123)
    if not Admin.query.filter_by(username='cmpquery@gmail.com').first():
        admin = Admin(username='cmpquery@gmail.com', password_hash=generate_password_hash('Admin@123'))
        db.session.add(admin)
        db.session.commit()

    # create default student if none exists (student/student123) to preserve dev login
    try:
        if not Student.query.filter_by(student_id='student').first():
            default_email = os.environ.get('DEFAULT_STUDENT_EMAIL', 'student@local')
            student = Student(student_id='student', name='Default Student', email=default_email, password=generate_password_hash('student123'))
            db.session.add(student)
            db.session.commit()
    except Exception:
        # If the students table isn't present yet, create_all and retry once
        try:
            db.create_all()
            if not Student.query.filter_by(student_id='student').first():
                default_email = os.environ.get('DEFAULT_STUDENT_EMAIL', 'student@local')
                student = Student(student_id='student', name='Default Student', email=default_email, password=generate_password_hash('student123'))
                db.session.add(student)
                db.session.commit()
        except Exception:
            app.logger.exception('Could not create default student')


def create_perfect_database():
    """Aggressive, deterministic DB reset:

    - Force delete the SQLite file and any WAL/SHM files
    - Run `db.create_all()` to create tables
    - Verify the `students` table has the required columns
    - Seed a default student if missing
    Returns True on success, False on failure.
    """
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_file = None
    if db_uri.startswith('sqlite:///'):
        db_file = db_uri.replace('sqlite:///', '')

    # Force-delete DB files for a clean slate
    if db_file:
        candidates = [db_file, f"{db_file}-wal", f"{db_file}-shm"]
        for fpath in candidates:
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
                    print(f"🗑️ FORCE DELETED {fpath}")
            except Exception as e:
                print(f"Failed to delete {fpath}: {e}")

    # Create tables and verify schema
    try:
        with app.app_context():
            db.create_all()
            print('✅ Tables created with PERFECT schema')

            inspector = inspect(db.engine)
            try:
                cols_info = inspector.get_columns('students')
            except Exception as e:
                print('❌ Could not inspect students table:', e)
                return False

            columns = [c['name'] for c in cols_info]
            required = ['id', 'student_id', 'name', 'email', 'password']
            if all(col in columns for col in required):
                print('✅ ALL columns verified: student_id exists')
            else:
                missing = [r for r in required if r not in columns]
                print('❌ MISSING COLUMNS - ABORT. Missing:', missing)
                return False

            # Seed default student if missing
            try:
                if not Student.query.filter_by(student_id='student').first():
                    default_email = os.environ.get('DEFAULT_STUDENT_EMAIL', 'student@local')
                    default_student = Student(
                        student_id='student',
                        name='Default Student',
                        email=default_email,
                        password=generate_password_hash('student123')
                    )
                    db.session.add(default_student)
                    db.session.commit()
                    print('✅ Default student/student123 created')
            except Exception as e:
                print('❌ Could not create default student:', e)
                return False

    except Exception as exc:
        print('Error creating perfect database:', exc)
        return False

    return True


def force_create_database():
    """Nuclear reset: drop students table, drop_all, create_all, verify columns.

    Returns True on success, False on failure.
    """
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    db_file = None
    if db_uri.startswith('sqlite:///'):
        db_file = db_uri.replace('sqlite:///', '')

    # Delete sqlite files first for a clean filesystem state
    if db_file:
        candidates = [db_file, f"{db_file}-wal", f"{db_file}-shm"]
        for fpath in candidates:
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
                    print(f"🗑️ DATABASE DESTROYED {fpath}")
            except Exception as e:
                print(f"Failed to delete {fpath}: {e}")

    try:
        with app.app_context():
            # Drop students table if it exists (defensive)
            try:
                db.session.execute(text("DROP TABLE IF EXISTS students"))
                db.session.commit()
                print('🔥 DROPPED students table')
            except Exception as e:
                print('Warning: could not DROP students table directly:', e)

            # Ensure metadata is cleared and then recreate tables
            db.drop_all()
            db.create_all()
            print('✅ Tables recreated')

            # Verify columns with inspector
            inspector = inspect(db.engine)
            try:
                cols = [c['name'] for c in inspector.get_columns('students')]
            except Exception as e:
                print('❌ Could not inspect students table:', e)
                return False

            print(f'🔍 ACTUAL columns: {cols}')
            required = ['id', 'student_id', 'name', 'email', 'password']
            missing = [c for c in required if c not in cols]
            if missing:
                print(f'❌ STILL MISSING: {missing}')
                return False

            print('✅ ALL COLUMNS PERFECT')

            # Seed default student if missing
            try:
                if not Student.query.filter_by(student_id='student').first():
                    default_email = os.environ.get('DEFAULT_STUDENT_EMAIL', 'student@local')
                    default_student = Student(
                        student_id='student',
                        name='Default Student',
                        email=default_email,
                        password=generate_password_hash('student123')
                    )
                    db.session.add(default_student)
                    db.session.commit()
                    print('✅ Default student created')
            except Exception as e:
                print('❌ Could not create default student:', e)
                return False

    except Exception as exc:
        print('Error in force_create_database:', exc)
        return False

    return True


@app.route('/fix-db')
def fix_database():
    """One-time helper to safely add missing columns to the `students` table.

    Usage: visit /fix-db once after upgrading the model. This will:
    - create the `students` table if missing
    - add missing `student_id` and `name` columns if absent
    - create a default student (student/student123) if missing
    """
    try:
        conn = db.engine.connect()
        # Ensure table exists with the required schema (no-op if already exists)
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT UNIQUE,
                name TEXT,
                email TEXT UNIQUE,
                password TEXT
            )
            """
        ))

        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(students)")).fetchall()]

        added = []
        if 'student_id' not in cols:
            # Add student_id column and unique index to avoid breaking existing rows
            conn.execute(text("ALTER TABLE students ADD COLUMN student_id TEXT"))
            # create unique index (if constraint enforcement required)
            try:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_student_id ON students(student_id)"))
            except Exception:
                app.logger.exception('Could not create unique index for student_id')
            added.append('student_id')

        if 'name' not in cols:
            conn.execute(text("ALTER TABLE students ADD COLUMN name TEXT DEFAULT 'Student'"))
            added.append('name')

        # Refresh columns
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(students)")).fetchall()]

        # Ensure default student exists
        try:
            if not Student.query.filter_by(student_id='student').first():
                from werkzeug.security import generate_password_hash as _gph
                default_email = os.environ.get('DEFAULT_STUDENT_EMAIL', 'student@local')
                default_student = Student(student_id='student', name='Default Student', email=default_email, password=_gph('student123'))
                db.session.add(default_student)
                db.session.commit()
                added.append('default_student')
        except Exception:
            app.logger.exception('Could not add default student row')

        conn.close()
        for a in added:
            flash(f'Added {a}', 'success')
    except Exception as exc:
        app.logger.exception('Error fixing DB schema: %s', exc)
        flash('Error fixing DB schema; see server logs', 'error')

    return redirect(url_for('student_login'))


# NOTE: auto-fix redirect and auto-fix route removed to avoid request-time redirects.
# Database schema fixes and table creation are handled at startup below.


# init_db via before_first_request removed. Initialization happens at process start.


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/submit_query', methods=['POST'])
def submit_query():
    name = request.form.get('name') or request.form.get('guest_name')
    email = request.form.get('email') or request.form.get('guest_email')
    # prefer category/message fields from student form; fallback to guest fields
    category = request.form.get('category')
    message = request.form.get('message') or request.form.get('guest_query')
    student_id = session.get('student_id')  # Attach student_id (numeric students.id) if logged in

    if not name or not email or not message:
        flash('All fields are required', 'error')
        return redirect(request.referrer or url_for('home'))
    # Normalize session student id to integer foreign key
    student_fk = None
    if student_id is not None:
        try:
            student_fk = int(student_id)
        except (TypeError, ValueError):
            # try to resolve legacy textual student_id to student row
            try:
                s = Student.query.filter_by(student_id=str(student_id)).first()
                if s:
                    student_fk = s.id
            except Exception:
                student_fk = None

    q = Query(name=name.strip(), email=email.strip(), category=(category.strip() if category else None), message=message.strip(), student_id=student_fk, status='Pending')
    db.session.add(q)
    db.session.commit()

    flash('Your query has been submitted successfully.', 'success')

    if student_id:
        return redirect(url_for('student_dashboard'))
    else:
        return redirect(url_for('home'))



@app.route('/guest-query', methods=['GET', 'POST'])
def guest_query():
    """Render guest query form (GET) and handle submissions (POST).

    This mirrors the behaviour of `/submit_query` while providing a named
    endpoint `guest_query` that templates reference.
    """
    if request.method == 'POST':
        # Reuse submit logic
        return submit_query()
    return render_template('guest_query.html')


@app.route('/admin-login', methods=['GET', 'POST'])
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        # Ensure default admin exists on first login attempt
        if not admin and username == 'cmpquery@gmail.com':
            try:
                default_admin = Admin.query.filter_by(username='cmpquery@gmail.com').first()
                if not default_admin:
                    default_admin = Admin(username='cmpquery@gmail.com', password_hash=generate_password_hash('Admin@123'))
                    db.session.add(default_admin)
                    db.session.commit()
                    app.logger.info('Default admin created with hash: %s', default_admin.password_hash)
                admin = default_admin
            except Exception:
                app.logger.exception('Error ensuring default admin exists')
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Logged in successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        # Log stored hashed password for debugging when login fails
        try:
            if admin:
                app.logger.info('Admin login failed for %s; stored hash=%s', username, admin.password_hash)
            else:
                # Log the would-be hash for the default password to help diagnose
                app.logger.info('No admin record found. Example hash(admin123)=%s', generate_password_hash('admin123'))
        except Exception:
            app.logger.exception('Error logging admin hash for debugging')
        flash('Invalid username or password', 'error')
        return render_template('admin_login.html'), 401
    return render_template('admin_login.html')

@app.route('/student-login', methods=['GET', 'POST'])
@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    """Temporary student login route.

    This mirrors the admin login flow for development. It uses a simple
    hard-coded credential check (student/student123). For production,
    replace this with a real Student model and proper authentication.
    """
    if request.method == 'POST':
        enrollment_no = request.form.get('enrollment_no', '').strip()
        student_course = request.form.get('student_course', '').strip()
        student_name = request.form.get('student_name', '').strip()

        if not enrollment_no or not student_course or not student_name:
            flash('All fields are required', 'error')
            return render_template('student_login.html'), 400

        match_found = False
        try:
            with open('student.csv', 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row['enrollment_no'].strip() == enrollment_no and
                        row['student_course'].strip() == student_course and
                        row['student_name'].strip() == student_name):
                        match_found = True
                        break
        except FileNotFoundError:
            flash('Student data not available. Contact administrator.', 'error')
            return render_template('student_login.html'), 400
        except Exception:
            flash('Login service temporarily unavailable.', 'error')
            return render_template('student_login.html'), 500

        if match_found:
            session['student_logged_in'] = True
            session['enrollment_no'] = enrollment_no
            session['student_course'] = student_course
            session['student_name'] = student_name
            
            # Lookup or create Student record for numeric ID (FK)
            student = Student.query.filter_by(student_id=enrollment_no).first()
            if not student:
                student = Student(
                    student_id=enrollment_no,
                    name=student_name,
                    email=f"{enrollment_no}@student.cmp",  # Dummy email
                    password=generate_password_hash('dummy')  # Dummy hash
                )
                db.session.add(student)
                db.session.commit()
            
            session['student_id'] = int(student.id)
            flash('Login successful!', 'success')
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid enrollment number, course, or name.', 'error')
            return render_template('student_login.html'), 401

    return render_template('student_login.html')



@app.route('/register', methods=['GET', 'POST'])
def register():
    # Minimal additive registration route; preserves existing flows
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        if not name or not email or not password:
            flash('All fields are required', 'error')
            return render_template('register.html'), 400
        # Check uniqueness by email
        if Student.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('register.html'), 409
        # Generate a textual student_id from name/email
        import re as _re
        base = _re.sub(r'[^a-z0-9]', '', name.split()[0].lower()) if name else ''
        if not base:
            base = _re.sub(r'[^a-z0-9]', '', email.split('@')[0].lower())
        candidate = base or 'student'
        suffix = 0
        while Student.query.filter_by(student_id=candidate).count() > 0:
            suffix += 1
            candidate = f"{base}{suffix}"
        hashed = generate_password_hash(password)
        s = Student(student_id=candidate, name=name, email=email, password=hashed)
        db.session.add(s)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('student_login'))
    return render_template('register.html')

def admin_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in as admin', 'error')
            return redirect(url_for('admin_login'))
        return fn(*args, **kwargs)

    return wrapper


def student_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('student_logged_in'):
            flash('Please log in as a student', 'error')
            return redirect(url_for('student_login'))
        return fn(*args, **kwargs)

    return wrapper

@app.route('/student_dashboard')
@app.route('/student-dashboard')
@student_required
def student_dashboard():
    # Retrieve queries for currently logged-in student using numeric FK
    sid = session.get('student_id')
    app.logger.debug('Rendering student dashboard for sid=%s', sid)
    sid_int = None
    try:
        if sid is not None:
            sid_int = int(sid)
    except (TypeError, ValueError):
        # attempt to resolve legacy textual student_id
        try:
            s = Student.query.filter_by(student_id=str(sid)).first()
            if s:
                sid_int = s.id
        except Exception:
            sid_int = None

    if sid_int is None:
        queries = []
    else:
        queries = Query.query.filter(Query.student_id == sid_int).order_by(Query.created_at.desc()).all()
    return render_template('student_dashboard.html', queries=queries)

@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    try:
        # Two sections: students (FK present) vs guests/alumni (no FK)
        student_queries = Query.query.filter(Query.student_id.isnot(None)).order_by(Query.created_at.desc()).all()
        guest_queries = Query.query.filter(Query.student_id.is_(None)).order_by(Query.created_at.desc()).all()
        return render_template('admin_dashboard.html', student_queries=student_queries, guest_queries=guest_queries)
    except OperationalError as e:
        app.logger.exception('OperationalError when loading admin_dashboard; attempting migration')
        try:
            with app.app_context():
                create_tables()
            student_queries = Query.query.filter(Query.student_id.isnot(None)).order_by(Query.created_at.desc()).all()
            guest_queries = Query.query.filter(Query.student_id.is_(None)).order_by(Query.created_at.desc()).all()
            return render_template('admin_dashboard.html', student_queries=student_queries, guest_queries=guest_queries)
        except Exception as e2:
            app.logger.exception('Migration attempt failed')
            return render_template('error.html', error=str(e2)), 500


@app.route('/api/admin/dashboard', methods=['GET'])
@admin_required
def admin_dashboard_data():
    """Return aggregated dashboard data for admin.

    counts: totals by status
    timeseries: per-day counts of queries created
    recent: last N queries (optional)
    """
    # Fetch all queries ordered by created_at desc
    queries = Query.query.order_by(Query.created_at.desc()).all()

    # Aggregate counts
    total = len(queries)
    pending = sum(1 for q in queries if (q.status or '').lower() == 'pending')
    in_progress = sum(1 for q in queries if (q.status or '').lower() in ('in-progress', 'in_progress', 'in progress'))
    resolved = sum(1 for q in queries if (q.status or '').lower() == 'resolved')

    # Build timeseries per day
    from collections import Counter
    from datetime import datetime

    def to_date_str(dt):
        if not dt:
            return None
        if isinstance(dt, str):
            try:
                # Try parse common format
                parsed = datetime.fromisoformat(dt)
                return parsed.date().isoformat()
            except Exception:
                return dt[:10]
        try:
            return dt.date().isoformat()
        except Exception:
            return None

    counter = Counter()
    for q in queries:
        d = to_date_str(getattr(q, 'created_at', None))
        if d:
            counter[d] += 1

    timeseries = [
        { 'date': k, 'count': counter[k] }
        for k in sorted(counter.keys())
    ]

    # Recent N queries
    N = 10
    recent = []
    for q in queries[:N]:
        recent.append({
            'id': q.id,
            'name': q.name,
            'email': q.email,
            'status': q.status,
            'created_at': to_date_str(getattr(q, 'created_at', None))
        })

    return jsonify({
        'counts': {
            'total': total,
            'pending': pending,
            'in_progress': in_progress,
            'resolved': resolved
        },
        'timeseries': timeseries,
        'recent': recent
    })


# ONLY ONE view_queries ROUTE - Removed the duplicate
@app.route('/view_queries', methods=['GET'])
@admin_required
def view_queries():
    try:
        queries = Query.query.order_by(Query.created_at.desc()).all()
        return render_template('view_queries.html', queries=queries)
    except OperationalError:
        app.logger.exception('OperationalError when loading view_queries; attempting migration')
        try:
            with app.app_context():
                create_tables()
            queries = Query.query.order_by(Query.created_at.desc()).all()
            return render_template('view_queries.html', queries=queries)
        except Exception as e:
            app.logger.exception('Migration attempt failed')
            return render_template('error.html', error=str(e)), 500


@app.route('/update_status', methods=['POST'])
@admin_required
def update_status():
    qid = request.form.get('query_id')
    status = request.form.get('status')
    response_text = request.form.get('response')
    q = Query.query.get(qid)
    if not q:
        flash('Query not found', 'error')
        return redirect(url_for('admin_dashboard'))
    q.status = status or q.status
    # update both legacy `response` and new `admin_response` to keep templates
    q.response = response_text or q.response
    q.admin_response = response_text or q.admin_response
    db.session.commit()
    # Send email notification to all query types (guest, student, alumni)
    try:
        if q.email and app.config.get('MAIL_USERNAME') and app.config.get('MAIL_PASSWORD'):
            msg = Message(
                subject=f"Your CMP Query Update – Status: {q.status}",
                sender=app.config.get('MAIL_DEFAULT_SENDER'),
                recipients=[q.email]
            )
            msg.body = f"""
Hello {q.name},

Your query has been updated.

Category: {q.category}
Message: {q.message}
Admin Response: {q.admin_response or q.response}
Status: {q.status}

Thank you,
CMP Admin Team
"""
            try:
                mail.send(msg)
                print(f"✅ EMAIL SENT SUCCESSFULLY to {q.email}")
            except Exception as e:
                print(f"❌ EMAIL FAILED for {q.email}: {str(e)}")
    except Exception as e:
        print(f"❌ EMAIL BLOCK ERROR: {str(e)}")
    flash('Query updated', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'success')
    return redirect(url_for('home'))


@app.route('/routes')
def list_routes():
    """Diagnostic: list all registered URL rules."""
    rules = []
    for rule in app.url_map.iter_rules():
        rules.append({
            'rule': str(rule),
            'endpoint': rule.endpoint,
            'methods': sorted([m for m in rule.methods if m not in ('HEAD', 'OPTIONS')])
        })
    return jsonify(sorted(rules, key=lambda r: r['rule']))


if __name__ == '__main__':
    # Aggressive startup: FORCE drop + recreate DB tables and verify schema.
    ok = force_create_database()
    if ok:
        print('🚀 CMP Query Portal - DATABASE PERFECT')
        app.run(debug=True)
    else:
        print('💥 FIX MODEL DEFINITION or inspect logs')
        sys.exit(1)