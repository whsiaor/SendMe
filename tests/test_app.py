import os
import tempfile
import pytest
from flask import url_for
from app import app, create_user, verify_user, db
from pymongo import MongoClient
import boto3
from moto import mock_s3
import sqlite3

# Fixtures
@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    app.config['DATABASE'] = db_path
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client

    os.close(db_fd)
    os.unlink(db_path)

def init_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, password_hash TEXT NOT NULL)''')
    conn.commit()
    conn.close()

@pytest.fixture
def mongo():
    client = MongoClient('mongodb://localhost:27017/')
    db = client.test_db
    yield db
    client.drop_database('test_db')
    client.close()

@mock_s3
@pytest.fixture
def s3_bucket():
    conn = boto3.client('s3')
    conn.create_bucket(Bucket='mybucket')
    yield conn
    conn.delete_bucket(Bucket='mybucket')


# Tests
def test_register(client):
    rv = client.post('/register', data=dict(
        username='testuser', password='testpass'
    ), follow_redirects=True)
    assert b'Registered!' in rv.data

def test_login(client):
    create_user('testuser', 'testpass')
    rv = client.post('/login', data=dict(
        username='testuser', password='testpass'
    ), follow_redirects=True)
    assert b'Welcome' in rv.data

def test_index(client):
    create_user('testuser', 'testpass')
    user = verify_user('testuser', 'testpass')
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
    rv = client.get('/')
    assert b'Messages' in rv.data

@mock_s3
def test_upload_file(client, s3_bucket):
    create_user('testuser', 'testpass')
    user = verify_user('testuser', 'testpass')
    with client.session_transaction() as sess:
        sess['user_id'] = user.id

    with open('testfile.txt', 'w') as f:
        f.write('This is a test file.')

    with open('testfile.txt', 'rb') as f:
        data = {
            'file': (f, 'testfile.txt'),
            'message': 'This is a test message'
        }
        rv = client.post('/submit', data=data, follow_redirects=True)

    assert b'testfile.txt' in rv.data
    assert b'This is a test message' in rv.data
    os.remove('testfile.txt')

def test_download_file(client, s3_bucket):
    create_user('testuser', 'testpass')
    user = verify_user('testuser', 'testpass')
    with client.session_transaction() as sess:
        sess['user_id'] = user.id

    # Upload a file to the mock S3
    s3_bucket.put_object(Bucket='mybucket', Key='testfile.txt', Body=b'This is a test file.')

    rv = client.get('/downloads/testfile.txt')
    assert rv.status_code == 200
    assert b'This is a test file.' in rv.data
