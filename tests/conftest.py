# conftest.py
import sqlite3
import pytest
from app import app


@pytest.fixture(scope='module')
def client():
    app.config['TESTING'] = True
    app.config['SQLITE_DB'] = 'tests/test.db'
    
    with app.test_client() as client:
        yield client

    
@pytest.fixture
def sqlite3_db():
    # Create an in-memory SQLite database
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL
    )
    ''')
    conn.commit()
    yield conn
    conn.close()

