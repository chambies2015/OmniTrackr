"""Regression tests for the September 2026 bug sweep.

Each test pins a bug that shipped: friends could not see music or books, a
missing custom tab returned 500, CSP-blocked inline handlers left friend search
dead, dashboard rows rendered titles as HTML, and custom tab items with a
metadata source or an uploaded poster failed to save.
"""
import re
from pathlib import Path

import httpx
import pytest

from app import auth, crud, models, schemas
from app import dashboard_assets

ROOT = Path(__file__).resolve().parents[1]
APP_JS = dashboard_assets.full_source()
AUTH_JS = (ROOT / "app" / "static" / "auth.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")


def _friend(db_session, authenticated_client, username="shelf_friend", **privacy):
    friend = crud.create_user(
        db_session,
        schemas.UserCreate(email=f"{username}@example.com", username=username, password="password123"),
        auth.get_password_hash("password123"),
    )
    for field, value in privacy.items():
        setattr(friend, field, value)
    db_session.add(models.Music(user_id=friend.id, title="Kid A", artist="Radiohead", year=2000, listened=True))
    db_session.add(models.Book(user_id=friend.id, title="Dune", author="Frank Herbert", year=1965, read=False))
    db_session.commit()
    me = authenticated_client.get("/account/me").json()["id"]
    crud.create_friendship(db_session, me, friend.id)
    return friend


# ---------------------------------------------------------------- friends: music & books

def test_friend_music_and_books_are_visible_to_friends(authenticated_client, db_session):
    friend = _friend(db_session, authenticated_client)

    music = authenticated_client.get(f"/friends/{friend.id}/music")
    books = authenticated_client.get(f"/friends/{friend.id}/books")

    assert music.status_code == 200
    assert music.json()["count"] == 1
    assert music.json()["music"][0]["artist"] == "Radiohead"
    assert books.status_code == 200
    assert books.json()["books"][0]["author"] == "Frank Herbert"
    profile = authenticated_client.get(f"/friends/{friend.id}/profile").json()
    assert profile["music_count"] == 1 and profile["books_count"] == 1


def test_private_friend_music_and_books_stay_private(authenticated_client, db_session):
    friend = _friend(db_session, authenticated_client, music_private=True, books_private=True)

    for path, label in (("music", "music"), ("books", "books")):
        response = authenticated_client.get(f"/friends/{friend.id}/{path}")
        assert response.status_code == 403
        assert f"made their {label} private" in response.json()["detail"]
    profile = authenticated_client.get(f"/friends/{friend.id}/profile").json()
    assert profile["music_count"] is None and profile["books_count"] is None


def test_friend_music_and_books_require_friendship(authenticated_client, db_session):
    stranger = crud.create_user(
        db_session,
        schemas.UserCreate(email="stranger2@example.com", username="stranger2", password="password123"),
        auth.get_password_hash("password123"),
    )
    for path in ("music", "books"):
        response = authenticated_client.get(f"/friends/{stranger.id}/{path}")
        assert response.status_code == 403
        assert "not friends" in response.json()["detail"].lower()


def test_friend_music_and_books_require_login(client):
    for path in ("music", "books"):
        assert client.get(f"/friends/1/{path}").status_code == 401


def test_friend_profile_modal_has_music_and_books_sections():
    for key, cap in (("music", "Music"), ("books", "Books")):
        assert f'data-toggle-accordion="{key}"' in INDEX_HTML
        for element_id in (f"{key}Icon", f"{key}Content", f"{key}Summary", f"friend{cap}Search", f"friend{cap}ListContainer"):
            assert INDEX_HTML.count(f'id="{element_id}"') == 1, element_id
    for loader in ("loadFriendMusic", "loadFriendBooks", "updateMusicSummary", "updateBooksSummary"):
        assert loader in APP_JS


# ---------------------------------------------------------------- CSP-safe markup

def test_dashboard_has_no_inline_event_handlers():
    """The strict CSP ignores on* attributes, so they silently do nothing."""
    assert not re.search(r"\son[a-z]+\s*=\s*\"", INDEX_HTML)


def test_friend_search_boxes_use_the_delegated_filter():
    for cap in ("Movies", "TVShows", "Anime", "VideoGames", "Music", "Books"):
        assert f'data-friend-filter="{cap}"' in INDEX_HTML
        assert f"window.filterFriend{cap} = function" in APP_JS
    assert "FRIEND_FILTERS.has(friendFilter)" in APP_JS


# ---------------------------------------------------------------- dashboard escaping

@pytest.mark.parametrize("unsafe", [
    "<td>${movie.title}</td>",
    "<td>${tvShow.title}</td>",
    "<td>${animeItem.title}</td>",
    "${item.title}</div>",
    "${director.director}</div>",
    "${show.title}</div>",
    "${genre.genre}</div>",
    '<div class="rating-bar-label">${genre}</div>',
    'href="${game.rawg_link}"',
    'href="${rawgLink}"',
])
def test_user_text_is_escaped_in_dashboard_markup(unsafe):
    assert unsafe not in APP_JS


def test_rawg_links_are_limited_to_http():
    assert "function safeHttpUrl(value)" in APP_JS
    assert APP_JS.count("safeHttpUrl(game.rawg_link)") >= 2
    assert "safeHttpUrl(rawgLink)" in APP_JS


def test_plain_text_assignments_are_not_double_escaped():
    assert not re.search(r"textContent = [^;\n]*escapeHtml\(", APP_JS)
    assert not re.search(r"\.alt = [^;\n]*escapeHtml\(", APP_JS)
    assert "altText = escapeHtml(altText)" not in APP_JS


def test_library_counts_use_singular_for_one():
    for noun in ("Movie", "TV Show", "Video Game", "Book"):
        assert f"`${{res.total}} {noun}${{res.total === 1 ? '' : 's'}}`" in APP_JS


# ---------------------------------------------------------------- custom tabs

def test_updating_a_missing_custom_tab_is_404_not_500(authenticated_client):
    response = authenticated_client.put("/custom-tabs/999999", json={"name": "Nope"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Custom tab not found"


def test_custom_tab_item_creation_has_no_undefined_references():
    # `token` was never defined, so every tab with a metadata source failed to add items.
    assert "posterUrl, token)" not in APP_JS
    # The poster file input was read outside its block scope after the form was cleared.
    assert "'pending_upload'" not in APP_JS
    assert APP_JS.count("await uploadCustomTabPoster(tab.id, item.id, posterFile);") == 2


def test_auth_script_defines_reactivation_helpers_once():
    assert AUTH_JS.count("function showReactivateOption(") == 1
    assert AUTH_JS.count("async function reactivateAccount(") == 1


# ---------------------------------------------------------------- proxies

def test_proxy_network_failures_are_gateway_timeouts(authenticated_client, monkeypatch):
    from app.main import app

    class FailingClient:
        async def get(self, *args, **kwargs):
            raise httpx.ProxyError("proxy refused")

        async def aclose(self):
            return None

    monkeypatch.setenv("RAWG_API_KEY", "test-key")
    monkeypatch.setattr(app.state, "external_api_client", FailingClient(), raising=False)
    response = authenticated_client.get("/api/proxy/rawg", params={"search": "Hades"})
    assert response.status_code == 504
    assert "connection error" in response.json()["detail"]
