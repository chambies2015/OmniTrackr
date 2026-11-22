"""Nov 22 2026 sweep of the "On your services" share links (PR #311).

Every test here fails on the code before the sweep:
- the link could not be turned off while the home card was hidden (three weeks) or the services were cleared,
- the owner opening their own paused link was told someone else had turned it off,
- the home card's link check rebuilt the whole shared list on every refresh,
- the card picture kept an old services or formats line after the list changed past its first six posters,
- the card picture's posters stopped short of the right margin.
"""
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from PIL import Image

from app import models, service_shares, streaming_services
from tests.test_service_shares import CHROME, cache, counting, headers, member, share_on, shared, stocked, where  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def test_owner_page_can_turn_the_link_off(client, db_session):
    user, path = shared(client, db_session)
    owner = client.get(path, headers=headers(user)).text
    assert "data-svc-off" in owner and "Turn off the link" in owner
    friend = member(db_session, "ruth")
    assert "data-svc-off" not in client.get(path, headers=headers(friend)).text
    assert "data-svc-off" not in client.get(path, headers=CHROME).text
    script = (ROOT / "app" / "static" / "services-share.js").read_text(encoding="utf-8")
    assert "'/api/streaming/share/off'" in script and "[data-svc-off]" in script


def test_owner_opening_a_paused_link_is_told_why(client, db_session):
    user, path = shared(client, db_session)
    # Two shelves private leaves two titles, under the minimum.
    user.tv_shows_private = True
    user.anime_private = True
    db_session.commit()
    mine = client.get(path, headers=headers(user))
    assert mine.status_code == 404 and "Your link is paused" in mine.text and "Fewer than three titles" in mine.text
    assert mine.headers["Cache-Control"] == "private, no-store"
    visitor = client.get(path, headers=CHROME)
    assert visitor.status_code == 404 and "isn&#x27;t shared anymore" in visitor.text and "paused" not in visitor.text
    friend = member(db_session, "ruth")
    assert "Your link is paused" not in client.get(path, headers=headers(friend)).text
    client.put("/api/streaming", json={"services": []}, headers=headers(user))
    mine = client.get(path, headers=headers(user))
    assert mine.status_code == 404 and "no streaming services picked" in mine.text


def test_home_card_keeps_a_paused_link_while_services_are_cleared(client, db_session):
    user, path = shared(client, db_session)
    card = client.put("/api/streaming", json={"services": []}, headers=headers(user)).json()["card"]
    assert card["state"] == "choose"
    assert card["share"]["path"] == path and card["share"]["allowed"] is False and card["share"]["reason"] == "services"
    off = client.post("/api/streaming/share/off", headers=headers(user))
    assert off.status_code == 200 and off.json()["share"]["path"] is None
    assert client.get("/api/streaming", headers=headers(user)).json()["card"]["share"] is None
    assert client.get(path, headers=CHROME).status_code == 404


def test_asking_card_without_a_link_skips_the_link_check(client, db_session, monkeypatch):
    user = stocked(client, db_session, services=())
    calls = []
    monkeypatch.setattr(service_shares, "state", lambda *args, **kwargs: calls.append(args) or {})
    card = client.get("/api/streaming", headers=headers(user)).json()["card"]
    assert card["state"] == "choose" and card["share"] is None and calls == []


def test_home_card_count_matches_the_page_without_building_it(client, db_session, monkeypatch):
    user = stocked(client, db_session)
    # A duplicate row, a title that left its service and a private shelf all count the way the page does.
    db_session.add(models.Movie(title="Past Lives", year=2023, watched=False, user_id=user.id))
    key = cache(db_session, "movie", "Gone Girl", 2014, where("Netflix"))
    db_session.add(models.Movie(title="Gone Girl", year=2014, watched=False, user_id=user.id))
    db_session.add(models.ServiceSighting(title_key=key, service="netflix", first_seen_at=datetime.utcnow() - timedelta(days=40),
                                          last_seen_at=datetime.utcnow() - timedelta(days=20), baseline=True,
                                          gone_at=datetime.utcnow() - timedelta(days=20)))
    db_session.commit()
    items, _ = service_shares.items_for(db_session, user)
    built = []
    monkeypatch.setattr(service_shares, "items_for", lambda *args, **kwargs: built.append(1) or ([], {}))
    share = service_shares.state(db_session, user)
    assert share["count"] == len(items) == 4 and built == []
    assert share["left_out"] == []
    user.anime_private = True
    db_session.commit()
    monkeypatch.undo()
    items, _ = service_shares.items_for(db_session, user)
    share = service_shares.state(db_session, user)
    assert share["count"] == len(items) == 3 and share["left_out"] == ["anime"]


def _data(kinds, services):
    items = [{"category": "movies", "title": f"Film {n}", "year": 2020, "image": None,
              "services": [{"id": "netflix", "name": "Netflix", "new": False}], "new": False} for n in range(6)]
    return {"total": 9, "new": 0, "by": None, "items": items, "kinds": kinds,
            "services": [{"id": service, "name": streaming_services.NAMES[service], "count": 1} for service in services]}


def test_picture_fingerprint_follows_the_services_and_formats_lines():
    base = service_shares.fingerprint(_data(["movies"], ["netflix"]))
    assert service_shares.fingerprint(_data(["movies"], ["netflix"])) == base
    # Same first six posters and totals, but a format or a service changed further down the list.
    assert service_shares.fingerprint(_data(["movies", "anime"], ["netflix"])) != base
    assert service_shares.fingerprint(_data(["movies"], ["netflix", "hulu"])) != base


def test_card_posters_reach_the_right_margin():
    data = {**_data(["movies"], ["netflix"]), "kinds": ["movies"]}
    image = Image.open(BytesIO(service_shares.render_card(data, {}))).convert("RGB")
    background = service_shares.BG
    # The last poster ends at the same 44px margin as the divider line under it.
    assert image.getpixel((1150, 300)) != background
    assert image.getpixel((1160, 300)) == background
    assert image.getpixel((40, 300)) == background and image.getpixel((48, 300)) != background

