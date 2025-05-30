from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import os
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24)  # Change this to a secure secret key in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hazard_reports.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

# Issue model
class Issue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='current')  # 'current' or 'fixed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    fixed_at = db.Column(db.DateTime, nullable=True)

# Create tables
with app.app_context():
    db.create_all()

# Login required decorator
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Admin required decorator
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user_type = data.get('userType')

    user = User.query.filter_by(username=username).first()
    
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        session['is_admin'] = user.is_admin
        
        # Redirect to admin dashboard if admin user
        if user.is_admin:
            return jsonify({'success': True, 'redirect': '/admin'})
        return jsonify({'success': True, 'redirect': '/'})
    
    return jsonify({'success': False, 'message': 'Invalid credentials'})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    # Check if username or email already exists
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already exists'})
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already exists'})

    # Create new user
    new_user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        is_admin=False
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    return render_template('index.html')

@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin.html')

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    user_message = request.json.get('message', '')
    
    # Send message to Rasa
    rasa_response = requests.post(
        'http://localhost:5005/webhooks/rest/webhook',
        json={'message': user_message}
    )
    
    if rasa_response.status_code == 200:
        bot_response = rasa_response.json()
        if bot_response:
            return jsonify({'response': bot_response[0].get('text', 'Sorry, I did not understand that.')})
    
    return jsonify({'response': 'Sorry, I am having trouble connecting to the server.'})

@app.route('/api/check-admin')
@login_required
def check_admin():
    return jsonify({'isAdmin': session.get('is_admin', False)})

@app.route('/api/issues', methods=['GET'])
def get_issues():
    current_issues = Issue.query.filter_by(status='current').all()
    fixed_issues = Issue.query.filter_by(status='fixed').order_by(Issue.fixed_at.desc()).limit(5).all()
    
    return jsonify({
        'current': [{'id': i.id, 'description': i.description, 'location': i.location, 'status': i.status} for i in current_issues],
        'fixed': [{'id': i.id, 'description': i.description, 'location': i.location, 'status': i.status} for i in fixed_issues]
    })

@app.route('/api/issues', methods=['POST'])
@login_required
def add_issue():
    data = request.get_json()
    new_issue = Issue(
        description=data['description'],
        location=data['location'],
        status='current'
    )
    db.session.add(new_issue)
    db.session.commit()
    return jsonify({'success': True, 'id': new_issue.id})

@app.route('/api/issues/<int:issue_id>/fix', methods=['POST'])
@admin_required
def fix_issue(issue_id):
    issue = Issue.query.get_or_404(issue_id)
    issue.status = 'fixed'
    issue.fixed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/issues/bot', methods=['POST'])
def add_issue_bot():
    print("Bot endpoint hit!")
    data = request.get_json()
    new_issue = Issue(
        description=data['description'],
        location=data['location'],
        status='current'
    )
    db.session.add(new_issue)
    db.session.commit()
    return jsonify({'success': True, 'id': new_issue.id})

@app.route('/api/issues/<int:issue_id>', methods=['DELETE'])
@admin_required
def delete_issue(issue_id):
    """Endpoint for admin to delete a specific issue."""
    issue = Issue.query.get_or_404(issue_id)
    db.session.delete(issue)
    db.session.commit()
    return jsonify({'success': True, "message": f"Issue {issue_id} deleted successfully."})

# Create admin user if not exists
def create_admin_user():
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),  # Change this in production
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()

create_admin_user()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
