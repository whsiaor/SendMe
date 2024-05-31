from werkzeug.security import generate_password_hash, check_password_hash
from app import load_user, create_user, verify_user, username_exists


def test_create_user(sqlite3_db):
    create_user('testuser', 'password123', conn=sqlite3_db)
    cursor = sqlite3_db.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', ('testuser',))
    user = cursor.fetchone()
    assert user is not None
    assert user[1] == 'testuser'
    assert check_password_hash(user[2], 'password123')

def test_verify_user(sqlite3_db):
    password_hash = generate_password_hash('password123', method='pbkdf2:sha256')
    cursor = sqlite3_db.cursor()
    cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', ('testuser', password_hash))
    sqlite3_db.commit()

    user = verify_user('testuser', 'password123', conn=sqlite3_db)
    assert user is not None
    assert user.username == 'testuser'

def test_username_exists(sqlite3_db):
    cursor = sqlite3_db.cursor()
    cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', ('testuser', 'dummy_hash'))
    sqlite3_db.commit()

    exists = username_exists('testuser', conn=sqlite3_db)
    assert exists

    not_exists = username_exists('nonexistent', conn=sqlite3_db)
    assert not not_exists

def test_load_user(sqlite3_db):
    cursor = sqlite3_db.cursor()
    cursor.execute('INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)', (1, 'testuser', 'dummy_hash'))
    sqlite3_db.commit()

    user = load_user(1, conn=sqlite3_db)
    assert user is not None
    assert user.username == 'testuser'

    user = load_user(2, conn=sqlite3_db)
    assert user is None
