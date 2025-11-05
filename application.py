from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime
import json
import requests
import csv
from io import StringIO
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure secret key
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Discord webhook configuration
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', 'https://discord.com/api/webhooks/1435539781944741968/HsZVHBugxy-0Zcun4NvRgCMBa6hbNfQeTtt1b82Nq0Ml9UjNYhQ6aSroRBUAMGZAjjU1')
last_alert_time = None

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('emotions.db')
    c = conn.cursor()
    c.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    if user:
        return User(id=user[0], username=user[1], email=user[2])
    return None

# Database setup
def init_db():
    conn = sqlite3.connect('emotions.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS emotions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  timestamp TEXT,
                  emotion TEXT,
                  probability REAL,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    conn.commit()
    conn.close()

init_db()

def send_discord_alert(user):
    """Send an alert to Discord when sad emotion is detected, rate limited to once per minute."""
    global last_alert_time
    current_time = datetime.now()
    if last_alert_time is None or (current_time - last_alert_time).total_seconds() >= 60:
        payload = {
            "content": f"🚨 Emergency Alert: Sad Emotion Detected for user {user.username} ({user.email})! Please check on the person."
        }
        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                print("✅ Discord alert sent successfully!")
                last_alert_time = current_time
            else:
                print(f"❌ Failed to send Discord alert: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Failed to send Discord alert: {e}")
    else:
        print("⏳ Alert rate limited: Not sending Discord alert (last sent less than 1 minute ago)")

def store_emotion(user_id, emotion, probability):
    conn = sqlite3.connect('emotions.db')
    c = conn.cursor()
    c.execute("INSERT INTO emotions (user_id, timestamp, emotion, probability) VALUES (?, ?, ?, ?)",
              (user_id, datetime.now().isoformat(), emotion, probability))
    conn.commit()
    conn.close()

def get_emotions_data(user_id=None):
    conn = sqlite3.connect('emotions.db')
    c = conn.cursor()
    if user_id:
        c.execute("SELECT timestamp, emotion, probability FROM emotions WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1000", (user_id,))
    else:
        c.execute("SELECT timestamp, emotion, probability FROM emotions ORDER BY timestamp DESC LIMIT 1000")
    data = c.fetchall()
    conn.close()
    return data

@app.route("/")
@login_required
def home():
    print("🌐 SERVER STARTED")
    return render_template("index.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_hash = generate_password_hash(password)

        conn = sqlite3.connect('emotions.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                      (username, email, password_hash))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('emotions.db')
        c = conn.cursor()
        c.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            user_obj = User(id=user[0], username=username, email='')  # Email not needed here
            login_user(user_obj)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

@socketio.on('my event')
def handle_my_event(json_data):
    if not current_user.is_authenticated:
        return
    print('📩 Received event data:', json_data)
    alert_sent = False  # Flag to prevent multiple alerts

    detections = json_data.get('data', [])
    for detection in detections:
        expressions = detection.get('expressions', {})

        # Store all emotions
        for emotion, prob in expressions.items():
            store_emotion(current_user.id, emotion, prob)

        sad_prob = expressions.get('sad', 0)
        neutral_prob = expressions.get('neutral', 0)

        # Adjusted logic: Trigger if sad > 0.5 and sad > neutral (to avoid false positives when neutral is high)
        if not alert_sent and sad_prob > 0.5 and sad_prob > neutral_prob:
            print("😢 Sad emotion detected! Sending alert...")
            send_discord_alert(current_user)
            alert_sent = True

            # Send cheerful message to the user
            emit('cheer_up', {
                'message': 'Hey there! Remember, every cloud has a silver lining. Smile, you’ve got this! 😊'
            })

    # Send back emotion data for real-time feedback
    emit('emotions', {
        'data': detections
    })

@app.route("/api/emotions")
def get_emotions():
    user_id = request.args.get('user_id')
    if user_id:
        data = get_emotions_data(int(user_id))
    else:
        data = get_emotions_data()
    return jsonify({"emotions": data})

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/export_emotions')
@login_required
def export_emotions():
    data = get_emotions_data(current_user.id)
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Timestamp', 'Emotion', 'Probability'])
    for row in data:
        writer.writerow(row)
    output = si.getvalue()
    si.close()
    response = app.response_class(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=emotions.csv'}
    )
    return response

if __name__ == '__main__':
    print("🚀 Starting Flask-SocketIO server...")
    socketio.run(app, host='0.0.0.0', port=5000)
