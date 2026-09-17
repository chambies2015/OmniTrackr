from html.parser import HTMLParser
from urllib.parse import urlsplit


class ScriptSources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script' and attrs.get('src'):
            self.sources.append(attrs['src'])


def test_dashboard_local_scripts_are_served(authenticated_client):
    parser = ScriptSources()
    parser.feed(authenticated_client.get('/').text)
    for src in parser.sources:
        if urlsplit(src).netloc:
            continue
        response = authenticated_client.get('/' + src.removeprefix('./').lstrip('/'))
        assert response.status_code == 200, src
        assert 'javascript' in response.headers['content-type'], src


def test_custom_tab_list_needs_no_redirect(authenticated_client):
    response = authenticated_client.get('/custom-tabs/', follow_redirects=False)
    assert response.status_code == 200
    assert response.json() == []


def test_first_book_survives_cookie_logout_and_login(authenticated_client, test_user_data):
    client = authenticated_client
    del client.headers['Authorization']  # Exercise the browser's cookie path.
    created = client.post('/books/', json={'title': 'First book', 'author': 'Sample author', 'year': 2024})
    assert created.status_code in (200, 201)
    book_id = created.json()['id']
    edited = client.put(f'/books/{book_id}', json={'rating': 8, 'review': 'Private reading note', 'review_public': False})
    assert edited.status_code == 200
    assert client.post('/auth/logout').status_code == 200
    assert 'data-public-shell="true"' in client.get('/').text
    assert client.get(f'/books/{book_id}').status_code == 401
    login = client.post('/auth/login', data={'username': test_user_data['username'], 'password': test_user_data['password']})
    assert login.status_code == 200
    restored = client.get(f'/books/{book_id}')
    assert restored.status_code == 200
    assert restored.json()['rating'] == 8
    assert restored.json()['review'] == 'Private reading note'
    assert restored.json()['review_public'] is False
    assert 'id="mainContainer"' in client.get('/').text
