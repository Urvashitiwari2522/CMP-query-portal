import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Query, Admin


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///cmp_queries.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret-change')

# initialize db
db.init_app(app)


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
            conn.execute(text("ALTER TABLE queries ADD COLUMN student_id VARCHAR(80)"))
            # ensure the DDL is persisted
            db.session.commit()
        conn.close()
    except Exception as exc:
        app.logger.exception('Error ensuring student_id column exists: %s', exc)
        try:
            db.session.rollback()
        except Exception:
            pass

    # create default admin if none exists (username: admin, password: admin123)
    if not Admin.query.filter_by(username='admin').first():
        admin = Admin(username='admin', password_hash=generate_password_hash('admin123'))
        db.session.add(admin)
        db.session.commit()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/submit_query', methods=['POST'])
def submit_query():
    # Handles guest and student submissions via POST
    name = request.form.get('guest_name') or request.form.get('name')
    email = request.form.get('guest_email') or request.form.get('email')
    message = request.form.get('guest_query') or request.form.get('message')

    if not name or not email or not message:
        flash('All fields are required', 'error')
        return redirect(request.referrer or url_for('home'))

    # If a student is logged in, attach their student_id to the query
    sid = session.get('student_id')
    q = Query(name=name.strip(), email=email.strip(), message=message.strip(), student_id=sid)
    db.session.add(q)
    db.session.commit()
    flash('Your query has been submitted successfully.', 'success')
    return redirect(request.referrer or url_for('home'))


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
        username = request.form.get('admin_id')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Logged in successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('admin_login.html')


@app.route('/student-login', methods=['GET', 'POST'])
@app.route('/student_login', methods=['GET', 'POST'])
def student_login():
    """Temporary student login route.

    This mirrors the admin login flow for development. It uses a simple
    hard-coded credential check (student/student123). For production,
    replace this with a real Student model and proper authentication.
    """
    error = None
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        password = request.form.get('password')
        # Dev-mode credentials
        if student_id == 'student' and password == 'student123':
            session['student_logged_in'] = True
            session['student_id'] = student_id
            flash('Logged in successfully', 'success')
            return redirect(url_for('home'))
        error = 'Invalid credentials'
        flash('Invalid credentials', 'error')
    return render_template('student_login.html', error=error)


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
@student_required
def student_dashboard():
    sid = session.get('student_id')
    queries = Query.query.filter_by(student_id=sid).order_by(Query.created_at.desc()).all()
    return render_template('student_dashboard.html', queries=queries)


@app.route('/admin_forgot_password', methods=['GET', 'POST'])
def admin_forgot_password():
    if request.method == 'POST':
        admin_id = request.form.get('admin_id')
        # In a real app we'd email a reset link. For now, just flash and
        # redirect back to admin login.
        flash('If an admin with that ID exists, a password reset link was sent.', 'info')
        return redirect(url_for('admin_login'))
    return render_template('admin_forgot_password.html')


@app.route('/student_forgot_password', methods=['GET', 'POST'])
def student_forgot_password():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        flash('If a student with that ID exists, a password reset link was sent.', 'info')
        return redirect(url_for('student_login'))
    return render_template('student_forgot_password.html')


@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    try:
        queries = Query.query.order_by(Query.created_at.desc()).all()
        return render_template('admin_dashboard.html', queries=queries)
    except OperationalError as e:
        # Try to run lightweight migration and retry once
        app.logger.exception('OperationalError when loading admin_dashboard; attempting migration')
        try:
            with app.app_context():
                create_tables()
            queries = Query.query.order_by(Query.created_at.desc()).all()
            return render_template('admin_dashboard.html', queries=queries)
        except Exception as e2:
            app.logger.exception('Migration attempt failed')
            return render_template('error.html', error=str(e2)), 500


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
    q.response = response_text or q.response
    db.session.commit()
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
    # Ensure DB tables exist before serving. Using an explicit app_context()
    # avoids relying on app.before_first_request which may not be available
    # in some environments or if the Flask import is non-standard.
    try:
        with app.app_context():
            create_tables()
    except Exception:
        # If initialization fails, we don't want to crash here while running
        # in a dev environment; surface the error when running normally.
        pass

    app.run(debug=True)
