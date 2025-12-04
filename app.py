import os
import sys
import logging
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from flask_mail import Mail, Message
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
import re
from dotenv import load_dotenv
from models import db, Query, Admin, Student, FAQ, BlockedEmail

app = Flask(__name__)
load_dotenv()
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///cmp_queries.db').replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret-change')

# Configure logging to file
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mail configuration (use environment variables in production)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'localhost')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 25))
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@local')
app.logger.info("SMTP Config: %s", app.config['MAIL_USERNAME'])

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

def send_guest_response_email(query_id, response_text):
    query = Query.query.get(query_id)
    if query and query.student_id is None and query.email:
        msg = Message(
            subject=f"CMP Query Response - {query.subject}",
            recipients=[query.email],
            sender=app.config['MAIL_DEFAULT_SENDER']
        )
        msg.body = f"""
Dear {query.name},

Your query has been answered:

Subject: {query.subject}
Category: {query.category or 'General'}
Response: {response_text}

Regards,
CMP Degree College Query Portal
"""
        try:
            mail.send(msg)
            app.logger.info("Email sent to %s", query.email)
            return True
        except Exception as e:
            app.logger.error("Email failed to %s: %s", query.email, str(e))
            return False

# 🆕 ADD THIS BLOCK HERE 👇
def fix_admins_table():
    """FIX: Add missing full_name column to admins table"""
    try:
        with app.app_context():
            conn = db.engine.connect()
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(admins)")).fetchall()]
            
            if 'full_name' not in cols:
                print("🛠️ Adding missing full_name column to admins table...")
                conn.execute(text("ALTER TABLE admins ADD COLUMN full_name TEXT"))
                conn.execute(text("""
                    UPDATE admins 
                    SET full_name = COALESCE(name, username) 
                    WHERE full_name IS NULL
                """))
                db.session.commit()
                print("✅ full_name column added and populated!")
            conn.close()
    except Exception as e:
        print(f"❌ Migration failed: {e}")

# Run fix on startup
with app.app_context():
    fix_admins_table()
# 🆕 END BLOCK 👆

# === NEW FEATURE: password reset token serializer ===
def get_serializer():
    secret = app.secret_key or os.environ.get('FLASK_SECRET', 'dev-secret-change')
    return URLSafeTimedSerializer(secret_key=secret, salt='cmp-reset')

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

    # create default admin if none exists (username: admin, password: admin123)
    if not Admin.query.filter_by(username='admin').first():
        admin = Admin(username='admin', password_hash=generate_password_hash('admin123'), name='Admin', full_name='Admin', email='admin@local')
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
                    print(f"ðŸ—‘ï¸ FORCE DELETED {fpath}")
            except Exception as e:
                print(f"Failed to delete {fpath}: {e}")

    # Create tables and verify schema
    try:
        with app.app_context():
            db.create_all()
            print('âœ… Tables created with PERFECT schema')

            inspector = inspect(db.engine)
            try:
                cols_info = inspector.get_columns('students')
            except Exception as e:
                print('âŒ Could not inspect students table:', e)
                return False

            columns = [c['name'] for c in cols_info]
            required = ['id', 'student_id', 'name', 'email', 'password']
            if all(col in columns for col in required):
                print('âœ… ALL columns verified: student_id exists')
            else:
                missing = [r for r in required if r not in columns]
                print('âŒ MISSING COLUMNS - ABORT. Missing:', missing)
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
                    print('âœ… Default student/student123 created')
            except Exception as e:
                print('âŒ Could not create default student:', e)
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
                    print(f"ðŸ—‘ï¸ DATABASE DESTROYED {fpath}")
            except Exception as e:
                print(f"Failed to delete {fpath}: {e}")

    try:
        with app.app_context():
            # Drop students table if it exists (defensive)
            try:
                db.session.execute(text("DROP TABLE IF EXISTS students"))
                db.session.commit()
                print('ðŸ”¥ DROPPED students table')
            except Exception as e:
                print('Warning: could not DROP students table directly:', e)

            # Ensure metadata is cleared and then recreate tables
            db.drop_all()
            db.create_all()
            print('âœ… Tables recreated')

            # Verify columns with inspector
            inspector = inspect(db.engine)
            try:
                cols = [c['name'] for c in inspector.get_columns('students')]
            except Exception as e:
                print('âŒ Could not inspect students table:', e)
                return False

            print(f'ðŸ” ACTUAL columns: {cols}')
            required = ['id', 'student_id', 'name', 'email', 'password']
            missing = [c for c in required if c not in cols]
            if missing:
                print(f'âŒ STILL MISSING: {missing}')
                return False

            print('âœ… ALL COLUMNS PERFECT')

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
                    print('âœ… Default student created')
            except Exception as e:
                print('âŒ Could not create default student:', e)
                return False

    except Exception as exc:
        print('Error in force_create_database:', exc)
        return False

    return True


# === NEW FEATURE: additive, idempotent schema migrations ===

def migrate_additive_schema():
    try:
        conn = db.engine.connect()
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info('queries')")).fetchall()]
        if 'admin_reply_text' not in cols:
            conn.execute(text("ALTER TABLE queries ADD COLUMN admin_reply_text TEXT"))
        if 'admin_reply_at' not in cols:
            conn.execute(text("ALTER TABLE queries ADD COLUMN admin_reply_at DATETIME"))
        if 'admin_reply_seen' not in cols:
            conn.execute(text("ALTER TABLE queries ADD COLUMN admin_reply_seen BOOLEAN DEFAULT 0"))
        if 'category' not in cols:
            conn.execute(text("ALTER TABLE queries ADD COLUMN category TEXT"))
            conn.execute(text("UPDATE queries SET category = 'other' WHERE category IS NULL"))
        db.session.commit()
        conn.close()
    except Exception:
        app.logger.exception('Migration error for queries columns')
    try:
        conn = db.engine.connect()
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info('students')")).fetchall()]
        if 'is_blocked' not in cols:
            conn.execute(text("ALTER TABLE students ADD COLUMN is_blocked BOOLEAN DEFAULT 0"))
            db.session.commit()
        conn.close()
    except Exception:
        app.logger.exception('Migration error for students.is_blocked')
    try:
        conn = db.engine.connect()
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info('admins')")).fetchall()]
        if 'name' not in cols:
            conn.execute(text("ALTER TABLE admins ADD COLUMN name TEXT"))
        if 'email' not in cols:
            conn.execute(text("ALTER TABLE admins ADD COLUMN email TEXT"))
        if 'is_active' not in cols:
            conn.execute(text("ALTER TABLE admins ADD COLUMN is_active BOOLEAN DEFAULT 1"))
        if 'is_blocked' not in cols:
            conn.execute(text("ALTER TABLE admins ADD COLUMN is_blocked BOOLEAN DEFAULT 0"))
        if 'created_at' not in cols:
            conn.execute(text("ALTER TABLE admins ADD COLUMN created_at DATETIME"))
        db.session.commit()
        conn.close()
    except Exception:
        app.logger.exception('Migration error for admins columns')
    try:
        db.create_all()
    except Exception:
        app.logger.exception('Error ensuring new tables exist')


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
    category = request.form.get('category') or 'other'
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

    # === NEW FEATURE: reject blocked users/emails ===
    if student_fk:
        try:
            s_obj = Student.query.get(student_fk)
            if s_obj and getattr(s_obj, 'is_blocked', False):
                flash('Your account has been blocked', 'error')
                return redirect(url_for('student_dashboard'))
        except Exception:
            pass
    else:
        try:
            if email and BlockedEmail.query.filter_by(email=email.strip().lower(), is_active=True).first():
                flash('This email is blocked from submitting queries', 'error')
                return redirect(url_for('home'))
        except Exception:
            pass

    q = Query(name=name.strip(), email=email.strip(), category=(category.strip() if category else None), message=message.strip(), student_id=student_fk, status='Pending')
    db.session.add(q)
    db.session.commit()

    # === FAQ AUTO-UPDATE LOGIC ===
    try:
        # Check for exact match on question/message in existing FAQs
        existing_faq = FAQ.query.filter_by(question=message.strip(), is_active=True).first()
        if existing_faq:
            # Increment frequency for existing FAQ
            existing_faq.frequency += 1
            db.session.commit()
        else:
            # Create new FAQ with frequency=1
            new_faq = FAQ(
                question=message.strip(),
                answer=None,
                frequency=1,
                category=(category.strip() if category else None),
                is_active=True
            )
            db.session.add(new_faq)
            db.session.commit()
    except Exception as e:
        app.logger.error('Error updating FAQ: %s', str(e))
        db.session.rollback()

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
        # FIX: Get from 'email' field (your HTML form) instead of 'admin_id'
        identifier = request.form.get('email', '').strip().lower()  # ← CHANGE 1
        password = request.form.get('password')
        
        # FIX: Try email first, then username fallback
        admin = Admin.query.filter_by(email=identifier).first() or Admin.query.filter_by(username=identifier).first()  # ← CHANGE 2
        
        # Rest of YOUR code stays EXACTLY SAME...
        if not admin and identifier == 'admin':  # ← Works for default too
            try:
                default_admin = Admin.query.filter_by(username='admin').first()
                if not default_admin:
                    default_admin = Admin(username='admin', password_hash=generate_password_hash('admin123'))
                    db.session.add(default_admin)
                    db.session.commit()
                    app.logger.info('Default admin created with hash: %s', default_admin.password_hash)
                admin = default_admin
            except Exception:
                app.logger.exception('Error ensuring default admin exists')
                
        if admin and check_password_hash(admin.password_hash, password):
            # Your existing block check code (perfect)
            try:
                if (hasattr(admin, 'is_active') and not admin.is_active) or (hasattr(admin, 'is_blocked') and admin.is_blocked):
                    flash('Your admin account is inactive or blocked', 'error')
                    return render_template('admin_login.html'), 403
            except Exception:
                pass
            session['admin_logged_in'] = True
            session['admin_username'] = admin.username  # ← Use admin.username (not identifier)
            try:
                session['admin_id'] = int(admin.id)
            except Exception:
                session['admin_id'] = None
            flash('Logged in successfully', 'success')
            return redirect(url_for('admin_dashboard'))
            
        flash('Invalid email or password', 'error')  # ← Updated message
        return render_template('admin_login.html'), 401
        
    return render_template('admin_login.html')
@app.route('/student-signup', methods=['GET', 'POST'])
@app.route('/student_signup', methods=['GET', 'POST'])
def student_signup():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # ✅ PASSWORD MATCH
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('student_signup.html'), 400

        # Rest of your code PERFECT (email validation, strong password, etc.)
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if not email_pattern.match(email):
            flash('Please provide a valid email address', 'error')
            return render_template('student_signup.html'), 400

        pw_pattern = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')
        if not pw_pattern.match(password):
            flash('Password must be 8+ chars: upper, lower, number, special char', 'error')
            return render_template('student_signup.html'), 400

        # Your existing DB + student_id logic (PERFECT)
        if Student.query.filter_by(email=email).count() > 0:
            flash('Email already registered', 'error')
            return render_template('student_signup.html'), 409

        base = re.sub(r'[^a-z0-9]', '', name.split()[0].lower()) if name else ''
        if not base: base = re.sub(r'[^a-z0-9]', '', email.split('@')[0].lower())
        candidate = base or 'student'
        suffix = 0
        while Student.query.filter_by(student_id=candidate).count() > 0:
            suffix += 1
            candidate = f"{base}{suffix}"

        hashed = generate_password_hash(password)
        student = Student(student_id=candidate, name=name, email=email, password=hashed)
        db.session.add(student)
        db.session.commit()

        flash('✅ Account created! Login below.', 'success')
        return redirect(url_for('student_login'))
    return render_template('student_signup.html')

@app.route('/student-login', methods=['GET', 'POST'])
@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        identifier = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        
        student = Student.query.filter_by(email=identifier).first() or Student.query.filter_by(student_id=identifier).first()
        
        if not student and identifier == 'student':
            try:
                default_student = Student.query.filter_by(student_id='student').first()
                if not default_student:
                    default_student = Student(student_id='student', name='Default Student', email='student@local', password=generate_password_hash('student123'))
                    db.session.add(default_student)
                    db.session.commit()
                student = default_student
            except Exception:
                app.logger.exception('Error ensuring default student exists')
                
        if student and check_password_hash(student.password, password):
            try:
                if hasattr(student, 'is_blocked') and student.is_blocked:
                    flash('Your account has been blocked', 'error')
                    return render_template('student_login.html'), 403
            except Exception:
                pass
            session['student_logged_in'] = True
            session['student_id'] = student.id
            session['student_name'] = student.name
            flash('Logged in successfully', 'success')
            return redirect(url_for('student_dashboard'))
            
        flash('Invalid email or student ID or password', 'error')
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
        queries = Query.query.filter_by(student_id=sid_int).order_by(Query.created_at.desc()).all()
    # mark unseen admin replies as seen
    try:
        for _q in queries:
            if _q.admin_reply_text and not _q.admin_reply_seen:
                _q.admin_reply_seen = True
        db.session.commit()
    except Exception:
        db.session.rollback()
    return render_template('student_dashboard.html', queries=queries)


@app.route('/admin_forgot_password', methods=['GET', 'POST'])
def admin_forgot_password():
    # send reset link via email
    if request.method == 'POST':
        identifier = (request.form.get('email') or request.form.get('admin_id') or '').strip()
        admin = None
        if identifier:
            if '@' in identifier:
                admin = Admin.query.filter_by(email=identifier.lower()).first()
            if not admin:
                admin = Admin.query.filter_by(username=identifier).first()
        if admin and getattr(admin, 'email', None):
            s = get_serializer()
            token = s.dumps({'role': 'admin', 'id': admin.id})
            link = url_for('admin_reset_password', token=token, _external=True)
            try:
                msg = Message(
                    subject="CMP Admin Password Reset",
                    sender=current_app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[admin.email]
                )
                msg.body = f"Click to reset your password: {link}"
                mail.send(msg)
                app.logger.info("Password reset email sent to admin %s", admin.email)
                flash('Reset link sent to your email.', 'success')
            except Exception as e:
                app.logger.error("Password reset email failed to admin %s: %s", admin.email, str(e))
                flash('Failed to send email, please try again or contact admin.', 'error')
        else:
            flash('If this account exists, a reset link has been sent.', 'info')
        return redirect(url_for('admin_login'))
    return render_template('admin_forgot_password.html')


@app.route('/admin_reset_password/<token>', methods=['GET', 'POST'])
def admin_reset_password(token):
    s = get_serializer()
    try:
        data = s.loads(token, max_age=3600)
        if data.get('role') != 'admin':
            raise BadSignature('Invalid role')
        admin = Admin.query.get(int(data.get('id')))
        if not admin:
            raise BadSignature('User missing')
    except (BadSignature, SignatureExpired):
        flash('Reset link is invalid or expired', 'error')
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        password = request.form.get('new_password') or ''
        confirm = request.form.get('confirm_password') or ''
        import re as _re
        if password != confirm:
            flash('Passwords do not match', 'error')
            return render_template('admin_reset_password.html')
        if not _re.match(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$', password):
            flash('Password must be 8+ chars with letters, digits, and special character', 'error')
            return render_template('admin_reset_password.html')
        admin.password_hash = generate_password_hash(password)
        db.session.commit()
        flash('Password updated. Please log in.', 'success')
        return redirect(url_for('admin_login'))
    return render_template('admin_reset_password.html')


@app.route('/student_forgot_password', methods=['GET', 'POST'])
def student_forgot_password():
    # send reset link via email
    if request.method == 'POST':
        identifier = (request.form.get('identifier') or '').strip()
        app.logger.debug('Forgot password requested for identifier=%s', identifier)
        if not identifier:
            flash('Identifier (student ID or email) is required', 'error')
            return redirect(url_for('student_forgot_password'))
        student = Student.query.filter_by(email=identifier.lower()).first() or Student.query.filter_by(student_id=identifier).first()
        if student:
            s = get_serializer()
            token = s.dumps({'role': 'student', 'id': student.id})
            link = url_for('student_reset_password', token=token, _external=True)
            try:
                msg = Message(
                    subject="CMP Student Password Reset",
                    sender=current_app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[student.email]
                )
                msg.body = f"Click to reset your password: {link}"
                mail.send(msg)
                app.logger.info("Password reset email sent to student %s", student.email)
            except Exception as e:
                app.logger.error("Password reset email failed to student %s: %s", student.email, str(e))
        flash('If this account exists, a reset link has been sent.', 'info')
        return redirect(url_for('student_login'))
    return render_template('student_forgot_password.html')


@app.route('/student_reset_password/<token>', methods=['GET', 'POST'])
def student_reset_password(token):
    s = get_serializer()
    try:
        data = s.loads(token, max_age=3600)
        if data.get('role') != 'student':
            raise BadSignature('Invalid role')
        student = Student.query.get(int(data.get('id')))
        if not student:
            raise BadSignature('User missing')
    except (BadSignature, SignatureExpired):
        flash('Reset link is invalid or expired', 'error')
        return redirect(url_for('student_login'))
    if request.method == 'POST':
        password = request.form.get('new_password') or ''
        confirm = request.form.get('confirm_password') or ''
        import re as _re
        if password != confirm:
            flash('Passwords do not match', 'error')
            return render_template('student_reset_password.html')
        if not _re.match(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$', password):
            flash('Password must be 8+ chars with letters, digits, and special character', 'error')
            return render_template('student_reset_password.html')
        student.password = generate_password_hash(password)
        db.session.commit()
        flash('Password updated. Please log in.', 'success')
        return redirect(url_for('student_login'))
    return render_template('student_reset_password.html')


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    try:
        # Two sections: students (FK present) vs guests/alumni (no FK)
        student_queries = Query.query.filter(Query.student_id != None).order_by(Query.created_at.desc()).all()
        guest_queries = Query.query.filter(Query.student_id == None).order_by(Query.created_at.desc()).all()
        students = Student.query.order_by(Student.name.asc()).all()
        return render_template('admin_dashboard.html', student_queries=student_queries, guest_queries=guest_queries, students=students)
    except OperationalError as e:
        app.logger.exception('OperationalError when loading admin_dashboard; attempting migration')
        try:
            with app.app_context():
                create_tables()
            student_queries = Query.query.filter(Query.student_id != None).order_by(Query.created_at.desc()).all()
            guest_queries = Query.query.filter(Query.student_id == None).order_by(Query.created_at.desc()).all()
            students = Student.query.order_by(Student.name.asc()).all()
            return render_template('admin_dashboard.html', student_queries=student_queries, guest_queries=guest_queries, students=students)
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
    from datetime import datetime as _dt

    def to_date_str(dt):
        if not dt:
            return None
        if isinstance(dt, str):
            try:
                # Try parse common format
                parsed = _dt.fromisoformat(dt)
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
    # Email guests; in-app notification for students
    if q.student_id is None:
        if q.email and app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD']:
            try:
                print(q.email)
                msg = Message(
                    subject=f"Your CMP Query Update â€“ Status: {status}",
                    sender=current_app.config['MAIL_DEFAULT_SENDER'],
                    recipients=[q.email]
                )
                msg.body = f"""
Hello {q.name},

Your query has been updated.

Category: {q.category}
Message: {q.message}
Admin Response: {q.admin_response}
Status: {status}

Thank you,
CMP Admin Team
"""
                mail.send(msg)
                app.logger.info("Status update email sent to %s", q.email)
            except Exception as e:
                app.logger.error("Status update email failed to %s: %s", q.email, str(e))
    else:
        # student: store admin reply metadata, do not send email
        try:
            q.admin_reply_text = (q.admin_response or response_text or '').strip()
            q.admin_reply_at = datetime.utcnow()
            q.admin_reply_seen = False
            db.session.commit()
        except Exception:
            db.session.rollback()
    flash('Query updated', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reply/<int:query_id>', methods=['POST'])
@admin_required
def admin_reply(query_id):
    response_text = request.form.get('response')
    query = Query.query.get(query_id)

    if query:
        query.status = 'responded'
        query.response = response_text
        db.session.commit()

        # EMAIL ONLY for guest queries
        if query.student_id is None:
            send_guest_response_email(query_id, response_text)

    flash('Response sent successfully!')
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


# === NEW FEATURE: Admin registration ===
@app.route('/admin_register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm_password') or ''
        if not name or not email or not password or not confirm:
            flash('All fields are required', 'error')
            return render_template('admin_register.html'), 400
        if password != confirm:
            flash('Passwords do not match', 'error')
            return render_template('admin_register.html'), 400
        import re as _re
        if not _re.match(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$', password):
            flash('Password must be 8+ chars with letters, digits, and special character', 'error')
            return render_template('admin_register.html'), 400
        if email and Admin.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('admin_register.html'), 409
        username = email or name.lower().replace(' ', '') or f"admin{int(datetime.utcnow().timestamp())}"
        if Admin.query.filter_by(username=username).first():
            username = f"{username}{int(datetime.utcnow().timestamp())}"
        admin = Admin(
            username=username,
            name=name,
            full_name=name,
            email=email,
            password_hash=generate_password_hash(password),
            is_active=True,
            is_blocked=False
        )
        db.session.add(admin)
        db.session.commit()
        flash('Admin registered. Please log in.', 'success')
        return redirect(url_for('admin_login'))
    return render_template('admin_register.html')


# === NEW FEATURE: Admin logout ===
@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    session.pop('admin_id', None)
    flash('Admin logged out', 'success')
    return redirect(url_for('admin_login'))


# === NEW FEATURE: Block/Unblock student ===
@app.route('/admin/students/<int:sid>/toggle_block', methods=['POST'])
@admin_required
def toggle_block_student(sid):
    s = Student.query.get_or_404(sid)
    s.is_blocked = not bool(s.is_blocked)
    db.session.commit()
    flash('Student block status updated', 'success')
    return redirect(url_for('admin_dashboard'))


# === NEW FEATURE: Block/Unblock guest email ===
@app.route('/admin/guests/toggle_block', methods=['POST'])
@admin_required
def toggle_block_guest():
    email = (request.form.get('email') or '').strip().lower()
    if not email:
        flash('Email required', 'error')
        return redirect(url_for('admin_dashboard'))
    b = BlockedEmail.query.filter_by(email=email).first()
    if not b:
        b = BlockedEmail(email=email, is_active=True)
        db.session.add(b)
    else:
        b.is_active = not bool(b.is_active)
    db.session.commit()
    flash('Guest email block status updated', 'success')
    return redirect(url_for('admin_dashboard'))


# === NEW FEATURE: Admin FAQ management ===
@app.route('/admin/faq', methods=['GET', 'POST'])
@admin_required
def admin_faq():
    if request.method == 'POST':
        q_text = (request.form.get('question') or '').strip()
        a_text = (request.form.get('answer') or '').strip()
        if not q_text:
            flash('Question is required', 'error')
        else:
            faq = FAQ(question=q_text, answer=a_text or None, is_active=True)
            db.session.add(faq)
            db.session.commit()
            flash('FAQ added', 'success')
    faqs = FAQ.query.order_by(FAQ.frequency.desc()).all()
    return render_template('admin_faq.html', faqs=faqs)


@app.route('/admin/faq/<int:fid>/toggle', methods=['POST'])
@admin_required
def toggle_faq(fid):
    f = FAQ.query.get_or_404(fid)
    f.is_active = not bool(f.is_active)
    db.session.commit()
    return redirect(url_for('admin_faq'))


@app.route('/admin/faq/<int:fid>/edit', methods=['POST'])
@admin_required
def edit_faq(fid):
    f = FAQ.query.get_or_404(fid)
    f.answer = (request.form.get('answer') or '').strip() or None
    db.session.commit()
    flash('FAQ updated', 'success')
    return redirect(url_for('admin_faq'))


# === NEW FEATURE: Create FAQ entry from a query ===
@app.route('/admin/queries/<int:qid>/mark_faq', methods=['POST'])
@admin_required
def mark_query_as_faq(qid):
    q = Query.query.get_or_404(qid)
    faq = FAQ(question=(q.message or '').strip()[:1000], answer=(q.admin_response or q.response or None), from_query_id=q.id, is_active=True)
    db.session.add(faq)
    db.session.commit()
    flash('Query added to FAQs', 'success')
    return redirect(url_for('admin_dashboard'))


# === NEW FEATURE: Public FAQ page ===
@app.route('/faq')
def faq_public():
    faqs = FAQ.query.filter_by(is_active=True).order_by(FAQ.frequency.desc()).all()
    return render_template('faq.html', faqs=faqs)

@app.route('/test-smtp')
def test_smtp():
    msg = Message("CMP Portal SMTP Test", recipients=[app.config['MAIL_USERNAME']])
    msg.body = "✅ SMTP working! Ready for guest responses."
    try:
        mail.send(msg)
        app.logger.info("SMTP test email sent successfully")
        return "✅ SMTP OK - Check your email!", 200
    except Exception as e:
        app.logger.error("SMTP test failed: %s", str(e))
        return f"❌ SMTP Error: {e}", 500


if __name__ == '__main__':
    # Safe startup: create tables and migrate schema if needed, preserve existing data
    try:
        with app.app_context():
            create_tables()
            migrate_additive_schema()
        print('CMP Query Portal - DATABASE READY')
        app.run(debug=True)
    except Exception as e:
        print(f'Error initializing database: {e}')
        sys.exit(1)
