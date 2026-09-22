"""Discover must be readable publicly and preserve existing libraries on save."""
import pytest
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
from app import models
from app.discover_catalog import MONTHLY_EDITIONS, TRAILS
from app.routers.collections import CATEGORIES


class DiscoverElements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_guest_save_links_return_to_the_exact_trail(client):
    paths = ['/discover/' + slug for slug in TRAILS]
    paths += ['/discover/monthly/' + slug for slug in MONTHLY_EDITIONS]
    for path in paths:
        elements = DiscoverElements(client.get(path).text).elements
        signin = next(attrs for tag, attrs in elements if attrs.get('id') == 'signin')
        url = urlsplit(signin['href'])
        assert url.path == '/' and not url.netloc
        assert url.fragment == 'landing-auth'
        assert parse_qs(url.query) == {'next': [path + '#save-picks']}
        assert any(attrs.get('id') == 'save-picks' for _, attrs in elements)


def test_discover_remains_readable_without_javascript(client):
    response = client.get('/discover')
    elements = DiscoverElements(response.text).elements
    cards = [attrs for tag, attrs in elements if tag == 'article' and 'data-search' in attrs]
    assert len(cards) == len(TRAILS)
    assert all('hidden' not in card for card in cards)
    filters = next(attrs for tag, attrs in elements if attrs.get('id') == 'trail-filters')
    assert 'hidden' in filters  # Controls appear only after their behavior is available.
    for trail in TRAILS.values():
        assert all(item['title'] in unescape(response.text) for item in trail['items'])
    assert '/static/ad-loader.js' not in response.text


def test_discover_search_metadata_is_escaped(client, monkeypatch):
    trail = next(iter(TRAILS.values()))
    monkeypatch.setitem(trail, 'name', '\"><img src=x onerror=alert(1)>')
    response = client.get('/discover')
    assert '<img src=x' not in response.text
    cards = [attrs for tag, attrs in DiscoverElements(response.text).elements if 'data-search' in attrs]
    assert trail['name'] in cards[0]['data-search']


def test_catalog_is_balanced_and_complete():
    assert len(TRAILS) == 10
    all_categories = set()
    for trail in TRAILS.values():
        items = trail['items']
        assert len(items) == 4
        assert len({item['key'] for item in items}) == len(items)
        assert len({item['category'] for item in items}) == len(items)
        assert all(item['why'] and item['caveat'] and item['source'] for item in items)
        all_categories.update(item['category'] for item in items)
    assert all_categories == set(CATEGORIES)
    assert len(MONTHLY_EDITIONS) == 1
    for edition in MONTHLY_EDITIONS.values():
        assert len(edition['items']) == 6
        assert {item['category'] for item in edition['items']} == set(CATEGORIES)
        assert edition['essay_title'] and edition['essay'] and edition['published']
        assert all(item['why'] and item['caveat'] and item['source'] for item in edition['items'])


def test_public_content_and_auth(client, db_session):
    index = client.get('/discover').text
    assert 'Follow your curiosity' in index
    for edition in MONTHLY_EDITIONS.values():
        assert edition['name'] in unescape(index)
    for slug, trail in TRAILS.items():
        page = client.get('/discover/' + slug)
        assert page.status_code == 200
        assert 'Content-Security-Policy' in page.headers
        assert trail['items'][0]['why'] in unescape(page.text)
        assert client.get(f'/api/discover/{slug}/preview').status_code == 401
        assert client.post(f'/api/discover/{slug}/save', json={'keys':[trail['items'][0]['key']]}).status_code == 401
    for slug, edition in MONTHLY_EDITIONS.items():
        page = client.get('/discover/monthly/' + slug)
        assert page.status_code == 200
        assert edition['essay_title'] in unescape(page.text)
        assert client.get(f'/api/discover/monthly/{slug}/preview').status_code == 401
        assert client.post(f'/api/discover/monthly/{slug}/save', json={'keys':[edition['items'][0]['key']]}).status_code == 401
    assert client.get('/discover/missing').status_code == 404
    assert client.get('/discover/monthly/missing').status_code == 404
    assert db_session.query(models.Collection).count() == 0
    sitemap = client.get('/sitemap.xml').text
    for slug in TRAILS:
        trail_page = client.get(f'/discover/{slug}')
        assert trail_page.headers['x-robots-tag'] == 'noindex, follow'
        assert '<meta name="robots" content="noindex, follow">' in trail_page.text
        assert f'/discover/{slug}' not in sitemap
    for slug in MONTHLY_EDITIONS:
        assert f'/discover/monthly/{slug}' in sitemap


@pytest.mark.parametrize('slug', list(MONTHLY_EDITIONS))
def test_monthly_edition_save_is_private_and_idempotent(authenticated_client, db_session, slug):
    user = db_session.query(models.User).first()
    edition = MONTHLY_EDITIONS[slug]
    items = edition['items']
    model = CATEGORIES[items[0]['category']][0]
    existing = model(user_id=user.id, title=items[0]['title'], rating=8.5, review='Keep this note', **items[0]['meta'])
    existing.watched = True
    db_session.add(existing)
    db_session.commit()
    base = f'/api/discover/monthly/{slug}'
    assert authenticated_client.get(base + '/preview').json()['items'][0]['existing']
    keys = [item['key'] for item in items]
    assert authenticated_client.post(base + '/save', json={'keys': keys}).json()['created'] == 5
    assert authenticated_client.post(base + '/save', json={'keys': keys}).json()['created'] == 0
    db_session.refresh(existing)
    assert existing.rating == 8.5
    assert existing.review == 'Keep this note'
    assert existing.watched is True
    collection = db_session.query(models.Collection).one()
    assert collection.name == 'Monthly Edition: ' + edition['name']
    assert len(collection.items) == len(items)


@pytest.mark.parametrize('slug', list(TRAILS))
def test_preview_save_repeat_preserve(authenticated_client, db_session, slug):
    user = db_session.query(models.User).first()
    items = TRAILS[slug]['items']
    model = CATEGORIES[items[0]['category']][0]
    existing = model(user_id=user.id, title=items[0]['title'], rating=9.2, review='My private note', **items[0]['meta'])
    existing.watched = True
    db_session.add(existing)
    db_session.commit()
    preview = authenticated_client.get(f'/api/discover/{slug}/preview').json()
    assert preview['items'][0]['existing']
    assert db_session.query(models.Collection).count() == 0
    keys = [i['key'] for i in items]
    for attempt in range(2):
        result = authenticated_client.post(f'/api/discover/{slug}/save', json={'keys':keys})
        assert result.status_code == 200
        assert result.json()['created'] == (len(items)-1 if attempt == 0 else 0)
    db_session.refresh(existing)
    assert existing.rating == 9.2
    assert existing.review == 'My private note'
    assert existing.watched is True
    assert db_session.query(models.Collection).count() == 1
    assert db_session.query(models.CollectionItem).count() == len(items)
    for i in items:
        assert db_session.query(CATEGORIES[i['category']][0]).filter_by(user_id=user.id).count() == 1


def test_selection_and_other_users(authenticated_client, db_session):
    other = models.User(username='other', email='other@example.com', hashed_password='unused')
    db_session.add(other)
    db_session.flush()
    db_session.add(models.Anime(user_id=other.id, title="Kiki's Delivery Service", review='Never expose this'))
    db_session.commit()
    base = '/api/discover/finding-your-feet'
    assert not authenticated_client.get(base+'/preview').json()['items'][0]['existing']
    assert authenticated_client.post(base+'/save', json={'keys':['unknown']}).status_code == 422
    assert authenticated_client.post(base+'/save', json={'keys':[]}).status_code == 422
    assert db_session.query(models.Collection).count() == 0
    assert authenticated_client.post(base+'/save', json={'keys':['kiki']}).json()['created'] == 1
    assert db_session.query(models.CollectionItem).count() == 1
    assert db_session.query(models.Book).count() == 0


def test_transaction_rollback(authenticated_client, db_session, monkeypatch):
    def fail():
        raise RuntimeError('simulated database failure')
    monkeypatch.setattr(db_session, 'commit', fail)
    with pytest.raises(RuntimeError):
        authenticated_client.post('/api/discover/finding-your-feet/save', json={'keys':['kiki']})
    assert db_session.query(models.Collection).count() == 0
    assert db_session.query(models.Anime).count() == 0
