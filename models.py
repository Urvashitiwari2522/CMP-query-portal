from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# === EXTENDED MODELS: additive fields only; backward-compatible ===
class Query(db.Model):
    __tablename__ = 'queries'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default='Pending')
    response = db.Column(db.Text, nullable=True)
    # optional admin reply stored explicitly
    admin_response = db.Column(db.Text, nullable=True)
    # === NEW FEATURE: in-app reply metadata for students ===
    admin_reply_text = db.Column(db.Text, nullable=True)
    admin_reply_at = db.Column(db.DateTime, nullable=True)
    admin_reply_seen = db.Column(db.Boolean, default=False)
    # Optional link to a logged-in student (store numeric students.id)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    # relationship to access the student if needed
    student = db.relationship('Student', backref=db.backref('queries', lazy=True))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'message': self.message,
            'status': self.status,
            'response': self.response,
            'created_at': self.created_at.isoformat()
        }



class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    # === NEW FEATURE: profile & flags ===
    name = db.Column(db.String(150), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    # Student model with a textual student_id (keeps backward compatibility
    # with the original dev credential 'student').
    student_id = db.Column(db.Text, unique=True, nullable=False)
    name = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text, unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)  # stores hashed password
    # === NEW FEATURE: block flag ===
    is_blocked = db.Column(db.Boolean, default=False)



# === NEW FEATURE: Manage blocked guest/alumni emails ===
class BlockedEmail(db.Model):
    __tablename__ = 'blocked_emails'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



# === NEW FEATURE: FAQ model ===
class FAQ(db.Model):
    __tablename__ = 'faqs'
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=True)
    frequency = db.Column(db.Integer, default=1)
    category = db.Column(db.String(100), nullable=True)
    from_query_id = db.Column(db.Integer, db.ForeignKey('queries.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


    from_query = db.relationship('Query', backref=db.backref('faqs', lazy=True))
