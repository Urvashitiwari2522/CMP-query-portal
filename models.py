from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


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
    email = db.Column(db.String(200), unique=True)
    password_hash = db.Column(db.String(200), nullable=False)


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    # Student model with a textual student_id (keeps backward compatibility
    # with the original dev credential 'student').
    student_id = db.Column(db.Text, unique=True, nullable=False)
    name = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text, unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)  # stores hashed password
