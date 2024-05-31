

def test_register_success(client, mocker):
    mocker.patch('app.username_exists', return_value=False)
    mocker.patch('app.create_user')

    response = client.post('/register', data={
        'username': 'testuser',
        'password': 'password123'
    }, follow_redirects=True)

    assert b'Registered!' in response.data

def test_register_existing_username(client, mocker):
    mocker.patch('app.username_exists', return_value=True)

    response = client.post('/register', data={
        'username': 'existing_user',
        'password': 'password123'
    }, follow_redirects=True)

    assert b'Username already exists.' in response.data

def test_register_invalid_username(client, mocker):
    mocker.patch('app.username_exists', return_value=False)

    response = client.post('/register', data={
        'username': 'invalid username!',
        'password': 'password123'
    }, follow_redirects=True)

    assert b'Username can only contain letters, numbers, and underscores.' in response.data

def test_register_short_password(client, mocker):
    mocker.patch('app.username_exists', return_value=False)

    response = client.post('/register', data={
        'username': 'testuser',
        'password': '123'
    }, follow_redirects=True)

    assert b'Password must be at least 6 characters.' in response.data

def test_register_empty(client, mocker):
    mocker.patch('app.username_exists', return_value=False)

    response = client.post('/register', data={
        'username': '',
        'password': ''
    }, follow_redirects=True)

    assert b'Username and password are required.' in response.data


def test_login_invalid_credentials(client, mocker):
    mocker.patch('app.verify_user', return_value=None)

    response = client.post('/login', data={
        'username': 'invalid_username',
        'password': 'invalid_password',
        'remember': 'on'
    }, follow_redirects=True)

    assert b'Invalid username or password' in response.data

def test_logout(client):
    response = client.get('/logout', follow_redirects=True)

    assert response.status_code == 200  
    assert b'Login' in response.data  
