import os
import re
from uuid import uuid4
from flask import Flask, flash, redirect, render_template, request, url_for, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
import boto3
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import pytz
import sqlite3


load_dotenv()

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['REMEMBER_COOKEI_DURATION'] = timedelta(days=30)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'secretkey') # for sqlite3
sqlite3_db = 'users.db'
socketio = SocketIO(app, cors_allowed_origins="*")

# MongoDB client
client = MongoClient('mongodb://mongodb:27017/')
db = client['snap']
messages = db['messages']

# S3 client
s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
)
s3_bucket_name = os.getenv('AWS_BUCKET_NAME')

local_timezone = timezone(timedelta(hours=10))

# Flask-login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id 
        self.username = username


@login_manager.user_loader
def load_user(user_id, conn=None):
    if conn is None:
        conn = sqlite3.connect(sqlite3_db)
    cursor = conn.cursor()
    cursor.execute('SELECT id, username FROM users WHERE id =?', (user_id,))
    user = cursor.fetchone()
    if conn is None:
        conn.close()
    if user:
        return User(id=user[0], username=user[1])
    return None


def create_user(username, password, conn=None):
    password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    if conn is None:
        conn = sqlite3.connect(sqlite3_db)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
    conn.commit()
    if conn is None:
        conn.close()


def verify_user(username, password, conn=None):
    if conn is None:
        conn = sqlite3.connect(sqlite3_db)
    cursor = conn.cursor()
    cursor.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,) )
    user = cursor.fetchone()
    if conn is None:
        conn.close()
    if user and check_password_hash(user[1], password):
        return User(id=user[0], username=username)


def username_exists(username, conn=None):
    if conn is None:
        conn = sqlite3.connect(sqlite3_db)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    if conn is None:
        conn.close()
    return user is not None


@app.route('/')
@login_required
def index():
    messages_list = [{
                'id': str(m['_id']),
                'message': m['message'], 
                'type': 'message', 
                'timestamp': m['uploadDate'] ,
                'batch_id': m['batch_id']} 
                for m in messages.find({'type': 'message'})]

    files = [{
                'id': str(f['_id']),
                'name': f['name'],
                'url': f['url'],
                'type': 'file', 
                'timestamp': f['uploadDate'] ,
                'batch_id': f['batch_id']}
                for f in messages.find({'type': 'file'})]
    

    items = files + messages_list
    items.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Group items by batch_id
    grouped_items = {}
    for item in items:
        batch_id = item['batch_id']
        if batch_id not in grouped_items:
            grouped_items[batch_id] = []
        grouped_items[batch_id].append(item)

    return render_template('index.html', grouped_items=grouped_items)


@app.route('/submit', methods=['POST'])
@login_required
def upload_it():
    message = request.form.get('message')
    files = request.files.getlist('file')

    timestamp = datetime.now(pytz.timezone('Australia/Brisbane')).strftime('%Y/%m/%d %H:%M:%S') # Ensure local timezone
    batch_id = str(uuid4())

    if message:
        messages.insert_one({
            'message': message,
            'type': 'message',
            'uploadDate': timestamp,
            'batch_id': batch_id
        })
        socketio.emit('new_message', {
            'message': message, 
            'type': 'message', 
            'timestamp': timestamp,
            'batch_id': batch_id
            }, to=None)

    for file in files:
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            s3.upload_fileobj(file, s3_bucket_name, filename)
            file_url = f"https://s3.{os.getenv('AWS_REGION')}.amazonaws.com/{os.getenv('AWS_BUCKET_NAME')}/{filename}"
            messages.insert_one({
                'name': filename,
                'url': file_url,
                'type': 'file',
                'uploadDate': timestamp,
                'batch_id': batch_id
            })
            socketio.emit('new_file', {
                'name': filename,
                'url': file_url,
                'type': 'file',
                'uploadDate': timestamp,
                'batch_id': batch_id
                }, to=None)


    return redirect(url_for('index'))


@app.route('/downloads/<filename>')
@login_required
def download_file(filename):
    try:
        response = s3.get_object(Bucket=s3_bucket_name, Key=filename)
        return send_file(
            response['Body'],
            as_attachment=True,
            download_name=filename
        )
    except s3.exceptions.NoSuchKey:
        return 'File not found', 404


@app.route('/delete_batch/<batch_id>', methods=['POST'])
@login_required
def delete_batch(batch_id):
    messages.delete_many({'batch_id': batch_id})

    s3_objects = s3.list_objects_v2(Bucket=s3_bucket_name).get('Contents', [])
    for obj in s3_objects:
        try:
            head_obj = s3.head_object(Bucket=s3_bucket_name, Key=obj['Key'])
            metadata = head_obj.get('Metadata', {})
            if metadata.get('batch_id') == batch_id:
                s3.delete_object(Bucket=s3_bucket_name, Key=obj['Key'])
        except Exception as e:
            print(f"Error deleting object {obj['Key']}: {e}")
    socketio.emit('delete_batch', {'batch_id': batch_id}, to=None)
    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        user = verify_user(username, password)
        if user:
            login_user(user, remember=remember)
            
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('register'))
        
        if len(username) < 3 or len(username) > 20:
            flash('Username must be between 3 and 20 characters.')
            return redirect(url_for('register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.')
            return redirect(url_for('register'))

        if not re.match("^[a-zA-Z0-9_]+$", username):
            flash('Username can only contain letters, numbers, and underscores.')
            return redirect(url_for('register'))
        
        if username_exists(username):
            flash('Username already exists.')
            return redirect(url_for('register'))
        
        create_user(username, password)
        flash('Registered!')
        return redirect(url_for('login'))

    return render_template('register.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000, allow_unsafe_werkzeug=True)