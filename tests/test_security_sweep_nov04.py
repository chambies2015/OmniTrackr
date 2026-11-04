"""Sweep of the Nov 3-4 merges: winter guides, phone shares, the gift guide and gift lists,
public page speed and the AdSense noindex pass."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from starlette.requests import Request

from app import migrations, site_traffic
from app.database import Base
from app.main import app
from app.routers import gift_guide

TOKEN = "AbCdEfGhIjKlMnOpQrStUv"


@pytest.fixture
def visitor():
    with TestClient(app) as other:
        yield other


def _list_with_one_gift(owner):
    owner.post("/api/gift-list/items", json={"source": "text", "text": "A book light"})
    data = owner.get("/api/gift-list").json()["list"]
    return data["path"].rsplit("/", 1)[1], data["items"][0]["id"]


class TestGiftClaimsStayHidden:
    """The undo route answered 200 for an open gift and 403 for a marked one when sent a made-up
    key, so anyone with the link (the owner included) could read which gifts were taken without
    marking anything. A wrong key now gets the same 403 either way."""

    def test_wrong_key_gets_the_same_answer_for_open_and_marked_gifts(self, authenticated_client, visitor):
        token, item_id = _list_with_one_gift(authenticated_client)
        url = f"/api/gifts/{token}/items/{item_id}/unclaim"
        guess = {"key": "x" * 32}

        open_answer = visitor.post(url, json=guess)
        visitor.post(f"/api/gifts/{token}/items/{item_id}/claim")
        marked_answer = visitor.post(url, json=guess)

        assert open_answer.status_code == marked_answer.status_code == 403
        assert open_answer.json() == marked_answer.json()

    def test_owner_cannot_use_the_undo_route_on_their_own_list(self, authenticated_client, visitor):
        token, item_id = _list_with_one_gift(authenticated_client)
        key = visitor.post(f"/api/gifts/{token}/items/{item_id}/claim").json()["key"]
        url = f"/api/gifts/{token}/items/{item_id}/unclaim"
        assert authenticated_client.post(url, json={"key": key}).status_code == 403
        # The person who marked it still can.
        assert visitor.post(url, json={"key": key}).status_code == 200


def test_every_gift_list_route_that_writes_or_reads_the_library_is_rate_limited():
    limited = {(path, method) for path, method in gift_guide_limits()}
    for route in gift_guide.router.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/"):
            continue
        for method in route.methods:
            assert (path, method) in limited, (path, method)
            assert hasattr(route.endpoint, "__wrapped__"), (path, method)


def gift_guide_limits():
    from app import main
    return main.GIFT_GUIDE_LIMITS.keys()


def _request(path):
    return Request({
        "type": "http", "method": "GET", "path": path, "query_string": b"",
        "headers": [(b"user-agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36"),
                    (b"accept", b"text/html")],
        "client": ("203.0.113.9", 5000), "scheme": "https", "server": ("omnitrackr.xyz", 443),
    })


class TestShareLinksStayOutOfSiteStats:
    """Opening a gift list, shared-list invite, poll or recap was counted under its full address,
    so every token sat in site_traffic_daily and showed on the Site stats page."""

    @pytest.mark.parametrize("path, counted", [
        (f"/gifts/{TOKEN}", "/gifts/(private link)"),
        (f"/lists/join/{TOKEN}", "/lists/join/(private link)"),
        (f"/tonight/{TOKEN}", "/tonight/(private link)"),
        (f"/recap/{TOKEN}/card.png", "/recap/(private link)/card.png"),
        (f"/join/{TOKEN}/", "/join/(private link)"),
        (f"/r/{TOKEN}", "/r/(private link)"),
        ("/tonight", "/tonight"),
        ("/holidays/gifts", "/holidays/gifts"),
        ("/u/someone", "/u/someone"),
    ])
    def test_paths_are_counted_without_the_token(self, path, counted):
        assert site_traffic.clean_path(path) == counted

    def test_server_side_page_counts_drop_the_token(self):
        recorder = site_traffic.TrafficRecorder()
        recorder.enabled = True
        assert recorder.record(_request(f"/gifts/{TOKEN}"), 200, "text/html; charset=utf-8")
        keys = [key for (_, kind, key) in recorder._pending if kind == "page"]
        assert keys == ["/gifts/(private link)"]

    def test_stored_rows_fold_into_one_row_per_page_and_day(self, tmp_path, monkeypatch):
        engine = create_engine(f"sqlite:///{(tmp_path / 'traffic.db').as_posix()}")
        Base.metadata.create_all(engine)
        monkeypatch.setattr(migrations, "engine", engine)
        day = date(2026, 11, 3)
        rows = [
            ("page", f"/gifts/{TOKEN}", 3),
            ("page", "/gifts/ZyXwVuTsRqPoNmLkJiHgFe", 2),
            ("human_page", f"/gifts/{TOKEN}", 1),
            ("page", f"/lists/join/{TOKEN}", 4),
            ("page", "/holidays/gifts", 9),
            ("source", "google.com", 5),
        ]
        with engine.connect() as conn:
            for kind, key, count in rows:
                conn.execute(text("INSERT INTO site_traffic_daily (day, kind, key, count) "
                                  "VALUES (:day, :kind, :key, :count)"),
                             {"day": day, "kind": kind, "key": key, "count": count})
            conn.commit()

        migrations.fold_private_link_pages()
        migrations.fold_private_link_pages()  # runs on every start; the second pass changes nothing

        with engine.connect() as conn:
            found = {(kind, key): count for kind, key, count in conn.execute(
                text("SELECT kind, key, count FROM site_traffic_daily")).fetchall()}
        engine.dispose()
        assert found == {
            ("page", "/gifts/(private link)"): 5,
            ("human_page", "/gifts/(private link)"): 1,
            ("page", "/lists/join/(private link)"): 4,
            ("page", "/holidays/gifts"): 9,
            ("source", "google.com"): 5,
        }
