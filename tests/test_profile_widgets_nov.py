"""November 2026 profile widgets: Right now, the forum signature, the badge, SVG copies, load counts,
the Settings panel and the Site stats block."""
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace

import pytest

from app import auth, models, profile_widgets
from app.middleware import PUBLIC_PROFILE_PATH
from app.site_traffic import RECORDER
from tests.test_public_profiles import enable, library, member


@pytest.fixture(autouse=True)
def fresh_widget_state(monkeypatch):
    profile_widgets.CACHE._items.clear()
    monkeypatch.setattr(profile_widgets.LOADS, "enabled", False)
    profile_widgets.LOADS._pending.clear()
    profile_widgets.LOADS._hosts.clear()
    yield
    profile_widgets.CACHE._items.clear()
    profile_widgets.LOADS._pending.clear()
    profile_widgets.LOADS._hosts.clear()


@pytest.fixture
def counters(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield lambda key: sum(n for (_, kind, name), n in RECORDER._pending.items() if kind == "widgets" and name == key)
    RECORDER._pending.clear()


def size_of(response):
    from PIL import Image
    return Image.open(BytesIO(response.content)).size


def svg_root(response):
    return ET.fromstring(response.content)


def svg_text(response) -> str:
    return " ".join(node.text or "" for node in svg_root(response).iter("{http://www.w3.org/2000/svg}text"))


def queue(db, user, category, item, started_days_ago=None, position=0):
    started = datetime.utcnow() - timedelta(days=started_days_ago) if started_days_ago is not None else None
    db.add(models.NextUpItem(user_id=user.id, category=category, item_id=item.id, position=position, started_at=started))
    db.commit()


def reader(db, name="nowfan", **profile):
    user = member(db, name)
    library(db, user)
    frieren = models.Anime(user_id=user.id, title="Frieren", watched=False)
    left_hand = models.Book(user_id=user.id, title="The Left Hand of Darkness", author="Le Guin", read=False)
    silksong = models.VideoGame(user_id=user.id, title="Silksong", played=False)
    db.add_all([frieren, left_hand, silksong])
    db.commit()
    queue(db, user, "anime", frieren, started_days_ago=6, position=0)
    queue(db, user, "books", left_hand, started_days_ago=1, position=1)
    queue(db, user, "video-games", silksong, position=2)
    return user, enable(db, user, **profile)


# ---------------------------------------------------------------- Right now

def test_now_widget_follows_the_right_now_switch(client, db_session):
    user, profile = reader(db_session)
    assert "now" not in profile_widgets.available(db_session, user, profile)
    assert client.get("/u/nowfan/widget/now.png").status_code == 404
    assert client.get("/u/nowfan/widget/now.svg").status_code == 404
    profile.show_now = True
    db_session.commit()
    response = client.get("/u/nowfan/widget/now.png")
    assert response.status_code == 200
    assert size_of(response) == (profile_widgets.WIDTH, profile_widgets.HEIGHTS["now"])
    data = profile_widgets.gather(db_session, user, profile, "now")
    # Started titles first, newest start first, then what's queued; never any progress.
    assert [row["title"] for row in data.rows] == ["The Left Hand of Darkness", "Frieren", "Silksong"]
    assert data.rows[0]["label"] == "Reading · Book" and data.rows[0]["note"].startswith("since ")
    assert data.rows[2]["label"].startswith("Up next")
    assert "progress" not in repr(data.rows).lower() and "episode" not in repr(data.rows).lower()


def test_turning_right_now_off_beats_the_cache(client, db_session):
    user, profile = reader(db_session, show_now=True)
    assert client.get("/u/nowfan/widget/now.svg").status_code == 200
    profile.show_now = False
    db_session.commit()
    assert client.get("/u/nowfan/widget/now.svg").status_code == 404


def test_private_categories_stay_off_right_now(db_session):
    user, profile = reader(db_session, "privatebooks", show_now=True)
    user.books_private = True
    db_session.commit()
    titles = [row["title"] for row in profile_widgets.gather(db_session, user, profile, "now").rows]
    assert "The Left Hand of Darkness" not in titles and "Frieren" in titles


# ---------------------------------------------------------------- signature and badge

def test_signature_and_badge_work_on_any_public_profile(client, db_session):
    user = member(db_session, "quietsig", statistics_private=True)
    library(db_session, user)
    profile = enable(db_session, user, show_favorites=False, show_stats=False)
    kinds = profile_widgets.available(db_session, user, profile)
    assert kinds == ["signature", "badge"]
    signature = client.get("/u/quietsig/widget/signature.png")
    assert signature.status_code == 200
    assert size_of(signature) == (profile_widgets.WIDTHS["signature"], profile_widgets.HEIGHTS["signature"])
    text = svg_text(client.get("/u/quietsig/widget/signature.svg"))
    assert "quietsig" in text and "tracked" not in text
    assert "Interstellar" not in text  # favorites are off and nothing is pinned
    badge = client.get("/u/quietsig/widget/badge.svg")
    assert "quietsig" in svg_text(badge) and "tracked" not in svg_text(badge)


def test_signature_names_what_the_profile_shows(client, db_session):
    user, profile = reader(db_session, "sigfan", show_now=True)
    data = profile_widgets.gather(db_session, user, profile, "signature")
    assert [(row["tag"], row["title"]) for row in data.rows] == [("Reading", "The Left Hand of Darkness"),
                                                                 ("Watching", "Frieren")]
    text = svg_text(client.get("/u/sigfan/widget/signature.svg"))
    assert "8 tracked" in text and "Frieren" in text
    profile.show_now = False
    db_session.commit()
    # With Right now off the queue stays private: the banner falls back to favorites.
    data = profile_widgets.gather(db_session, user, profile, "signature")
    assert [row["title"] for row in data.rows] == ["Secret Diary", "Interstellar"]  # rated 10, newest first
    assert "Frieren" not in svg_text(client.get("/u/sigfan/widget/signature.svg"))


def test_badge_counts_follow_library_counts(client, db_session):
    user = member(db_session, "badgefan")
    library(db_session, user)
    profile = enable(db_session, user)
    assert profile_widgets.gather(db_session, user, profile, "badge").message == "5 tracked"
    png = client.get("/u/badgefan/widget/badge.png?scale=2")
    width, height = size_of(png)
    assert height == 40 and 120 < width < 300
    profile.show_stats = False
    db_session.commit()
    assert profile_widgets.gather(db_session, user, profile, "badge").message == "badgefan"


# ---------------------------------------------------------------- SVG

def test_svg_widgets_are_safe_standalone_documents(client, db_session):
    user = member(db_session, "svgfan")
    db_session.add(models.Movie(user_id=user.id, title='<script>alert("x")</script>‮evil\x07', director="d",
                                year=2020, rating=10, watched=True))
    db_session.commit()
    enable(db_session, user)
    for kind in ("favorites", "signature", "stats", "badge"):
        response = client.get(f"/u/svgfan/widget/{kind}.svg?theme=auto")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/svg+xml"
        assert response.headers["content-security-policy"] == profile_widgets_router().SVG_POLICY
        assert response.headers["x-content-type-options"] == "nosniff"
        root = svg_root(response)  # Parses as XML: nothing unescaped got through.
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert b"<script" not in response.content and b"\x07" not in response.content
        assert b"\xe2\x80\xae" not in response.content  # no right-to-left override
    favorites = client.get("/u/svgfan/widget/favorites.svg")
    assert '<script>alert("x")</script>evil' in svg_text(favorites)
    assert b"prefers-color-scheme" not in favorites.content
    auto = client.get("/u/svgfan/widget/favorites.svg?theme=auto")
    assert b"@media (prefers-color-scheme:light)" in auto.content
    root = svg_root(auto)
    assert root.get("width") == "720" and root.get("height") == "280"
    # Unknown options fall back instead of failing.
    assert client.get("/u/svgfan/widget/favorites.svg?theme=neon").status_code == 200


def profile_widgets_router():
    from app.routers import profile_widgets as router
    return router


def test_unchanged_widgets_answer_304(client, db_session, counters):
    user = member(db_session, "etagfan")
    library(db_session, user)
    enable(db_session, user)
    first = client.get("/u/etagfan/widget/signature.png")
    etag = first.headers["etag"]
    again = client.get("/u/etagfan/widget/signature.png", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.content == b""
    assert again.headers["etag"] == etag and again.headers["cache-control"] == "public, max-age=900"
    assert client.get("/u/etagfan/widget/signature.png", headers={"If-None-Match": '"other"'}).status_code == 200
    assert counters("served_png") == 2 and counters("not_modified") == 1


def test_new_widget_addresses_pass_the_bot_filter():
    for path in ("/u/admin_fan/widget/now.svg", "/u/x/widget/signature.png", "/u/id/4/widget/badge.svg"):
        assert PUBLIC_PROFILE_PATH.match(path)
    assert not PUBLIC_PROFILE_PATH.match("/u/x/widget/now.php")


# ---------------------------------------------------------------- where widgets load

def fake_request(referer=None, agent="Mozilla/5.0 (Windows NT 10.0) Chrome/130.0"):
    headers = {"user-agent": agent}
    if referer is not None:
        headers["referer"] = referer
    return SimpleNamespace(headers=headers)


def test_embed_host_keeps_only_the_site_name():
    host = profile_widgets.embed_host
    assert host(fake_request("https://www.myanimelist.net/forum/?topicid=1&secret=yes")) == "myanimelist.net"
    assert host(fake_request("https://omnitrackr.xyz/u/dan/widgets")) is None  # our own preview
    assert host(fake_request("http://localhost:8000/")) is None
    assert host(fake_request(None, "github-camo (876543)")) == "github.com"
    assert host(fake_request(None, "Mozilla/5.0 (compatible; Discordbot/2.0)")) == "discord.com"
    assert host(fake_request("https://example.com/", "Googlebot-Image/1.0")) is None
    assert host(fake_request()) == ""
    assert host(fake_request("https://bad_host!.example/")) == profile_widgets.OTHER_HOST


def test_loads_are_counted_per_member_and_site(client, db_session, monkeypatch, counters):
    monkeypatch.setattr(profile_widgets.LOADS, "enabled", True)
    monkeypatch.setattr(profile_widgets.LOADS, "flush_interval", 0)
    user = member(db_session, "loadfan")
    library(db_session, user)
    enable(db_session, user)
    client.get("/u/loadfan/widget/signature.png", headers={"Referer": "https://myanimelist.net/forum/123"})
    client.get("/u/loadfan/widget/signature.svg", headers={"Referer": "https://myanimelist.net/profile/me"})
    client.get("/u/loadfan/widget/badge.svg", headers={"User-Agent": "github-camo (1)"})
    client.get("/u/loadfan/widget/badge.svg", headers={"Referer": "https://omnitrackr.xyz/u/loadfan/widgets"})
    rows = {(row.kind, row.host): row.loads for row in db_session.query(models.ProfileWidgetLoad).all()}
    assert rows == {("signature", "myanimelist.net"): 2, ("badge", "github.com"): 1}
    assert counters("preview") == 1
    summary = profile_widgets.owner_summary(db_session, user.id)
    assert summary["loads"] == 3 and summary["sites"] == ["myanimelist.net", "github.com"]
    assert profile_widgets.summary_sentence(summary) == (
        "Your widgets were loaded 3 times in the last 7 days, on myanimelist.net and github.com.")


def test_made_up_referrers_cannot_flood_a_member(db_session):
    counter = profile_widgets.LoadCounter()
    counter.enabled = True
    for index in range(profile_widgets.HOSTS_PER_MEMBER_DAY + 5):
        counter.add(7, "badge", f"site{index}.example")
    hosts = {key[3] for key in counter._pending}
    assert len(hosts) == profile_widgets.HOSTS_PER_MEMBER_DAY + 1
    assert counter._pending[(key := next(k for k in counter._pending if k[3] == profile_widgets.OTHER_HOST))] == 5
    assert key[1] == 7
    assert not counter.add(7, "nope", "x.example")


def test_load_rows_go_when_the_account_goes(db_session):
    from app import account_removal
    user, owner = member(db_session, "gonefan"), member(db_session, "siteowner")
    db_session.add(models.ProfileWidgetLoad(user_id=user.id, day=date.today(), kind="badge", host="", loads=3))
    db_session.commit()
    plan = account_removal.plan_for(db_session, user, owner)
    assert plan.removes["profile_widget_loads"] and not plan.blocked


# ---------------------------------------------------------------- Settings panel and counters

def test_settings_panel_endpoint(client, db_session, counters):
    user = member(db_session, "panelfan")
    library(db_session, user)
    headers = {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}
    assert client.get("/api/profile/widgets", headers=headers).json() == {"enabled": False}
    enable(db_session, user)
    response = client.get("/api/profile/widgets", headers=headers)
    data = response.json()
    assert response.headers["cache-control"] == "private, no-store"
    assert data["enabled"] is True and data["page"] == "/u/panelfan/widgets"
    assert data["preview"] == "/u/panelfan/widget/signature.png?scale=2"
    assert data["forum_code"] == ("[url=https://omnitrackr.xyz/u/panelfan?utm_source=profile-widget]"
                                  "[img]https://omnitrackr.xyz/u/panelfan/widget/signature.png[/img][/url]")
    assert data["summary"].startswith("Nobody has loaded your widgets")
    assert counters("settings_shown") == 1
    assert client.get("/api/profile/widgets").status_code == 401


def test_copy_events_count_only_known_keys(client, counters):
    assert client.post("/api/widgets/event", json={"key": "copy_anilist"}).status_code == 204
    assert client.post("/api/widgets/event", json={"key": "served_png"}).status_code == 204
    assert client.post("/api/widgets/event", json={"key": "made_up"}).status_code == 204
    assert counters("copy_anilist") == 1 and counters("served_png") == 0
    assert client.post("/api/widgets/event", json={"key": "x" * 41}).status_code == 422


def test_site_stats_block(db_session):
    one, two = member(db_session, "statone"), member(db_session, "stattwo")
    today = date.today()
    db_session.add_all([
        models.ProfileWidgetLoad(user_id=one.id, day=today, kind="signature", host="myanimelist.net", loads=9),
        models.ProfileWidgetLoad(user_id=two.id, day=today, kind="signature", host="myanimelist.net", loads=2),
        models.ProfileWidgetLoad(user_id=two.id, day=today - timedelta(days=20), kind="badge", host="", loads=4),
        models.ProfileWidgetLoad(user_id=two.id, day=today - timedelta(days=60), kind="badge", host="old.example", loads=50),
        models.SiteTrafficDaily(day=today, kind="source", key="profile-widget", count=6),
        models.SiteTrafficDaily(day=today, kind="human_source", key="profile-widget", count=4),
        models.SiteTrafficDaily(day=today, kind="widgets", key="copy_bbcode", count=3),
    ])
    db_session.commit()
    data = profile_widgets.stats(db_session, 30, datetime.utcnow())
    assert data["loads"] == 15 and data["members"] == 2 and data["members_7d"] == 2
    assert data["hosts"][0] == {"host": "myanimelist.net", "count": 11, "members": 2}
    assert {"host": profile_widgets.host_label(""), "count": 4, "members": 1} in data["hosts"]
    assert data["visits"] == 6 and data["people"] == 4
    assert data["counts"]["copy_bbcode"] == 3
    assert next(row for row in data["by_kind"] if row["kind"] == "signature")["count"] == 11


# ---------------------------------------------------------------- embed page

def test_embed_page_offers_every_pairing(client, db_session, counters):
    user, _ = reader(db_session, "pagefan", show_now=True)
    response = client.get("/u/pagefan/widgets")
    html = response.text
    assert counters("page_guest") == 1
    assert 'data-widget-format="svg"' in html and 'data-widget-theme="auto"' in html
    assert html.index('data-widget-kind="signature"') < html.index('data-widget-kind="now"') < html.index(
        'data-widget-kind="stats"')
    assert "[ img540(https://omnitrackr.xyz/u/pagefan/widget/signature.png?scale=2) ]" in html
    blob = re.search(r'<script type="application/json" id="widgetCodes"[^>]*>(.*?)</script>', html, re.S).group(1)
    assert "<" not in blob
    codes = json.loads(blob)
    assert set(codes) == {"signature", "now", "recent", "stats", "favorites", "badge"} - {"recent"}
    assert set(codes["now"]) == {"dark-png", "light-png", "dark-svg", "light-svg", "auto-svg"}
    assert codes["now"]["auto-svg"]["markdown"] == ("[![What pagefan is into right now on OmniTrackr]"
                                                     "(https://omnitrackr.xyz/u/pagefan/widget/now.svg?theme=auto)]"
                                                     "(https://omnitrackr.xyz/u/pagefan?utm_source=profile-widget)")
    assert codes["badge"]["dark-png"]["preview"] == "/u/pagefan/widget/badge.png?scale=2"
    assert 'height="20"' in codes["badge"]["dark-svg"]["html"] and "width=" not in codes["badge"]["dark-svg"]["html"]


def test_owner_sees_loads_and_right_now_hint(client, db_session, counters):
    user = member(db_session, "ownerloads")
    library(db_session, user)
    enable(db_session, user)
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(user))
    try:
        page = client.get("/u/ownerloads/widgets").text
    finally:
        client.cookies.clear()
    assert 'id="widgetLoads"' in page and "Nobody has loaded your widgets" in page
    assert "Right now appears when you switch on Right now." in page
    assert counters("page_owner") == 1
