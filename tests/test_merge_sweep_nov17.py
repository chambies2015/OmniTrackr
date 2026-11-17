"""Sweep of the Nov 17 2026 merges: admin account removal (#231), phone polish (#232), the check-in
email and page (#233), tracker guide content (#234), the Grammys ballot (#235), shared tier lists
(#236) and the sample library content pass (#237)."""
import asyncio
from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import event

from app import check_in, comeback, funnel, models, tier_list, tier_list_shares
from app.main import app
from app.routers import check_in as check_in_router
from app.routers import tier_list as tier_list_router
from tests.conftest import engine
from tests.test_check_in import NOW, member, save
from tests.test_security_sweep_nov06 import _limited
from tests.test_tier_list_shares import board


def _count_sql(run):
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        result = run()
    finally:
        event.remove(engine, "before_cursor_execute", record)
    return result, statements


PERSON = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/140.0"}


# ---------------------------------------------------------------- rate limits

def test_every_check_in_and_shared_tier_list_route_is_rate_limited():
    for route in check_in_router.router.routes:
        for method in route.methods:
            assert _limited(check_in_router.router, route.path, method), (method, route.path)
    for route in tier_list_router.router.routes:
        if route.path == "/tier-list":
            continue  # the maker page itself writes nothing
        for method in route.methods:
            assert _limited(tier_list_router.router, route.path, method), (method, route.path)


# ---------------------------------------------------------------- shared tier list views

def test_link_unfurlers_and_prefetches_are_not_counted_as_views(client, db_session, monkeypatch):
    tier_list.clear_cache()
    recorded = []
    monkeypatch.setattr(funnel, "record", lambda name, request=None: recorded.append(name) or True)
    made = client.post("/api/tier-list/shares", json=board()).json()
    with TestClient(app) as other:
        for agent in ("Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)",
                      "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)", "facebookexternalhit/1.1", ""):
            assert other.get(made["path"], headers={"user-agent": agent}).status_code == 200
        other.get(made["path"], headers={**PERSON, "sec-purpose": "prefetch;prerender"})
        share = db_session.query(models.TierListShare).one()
        db_session.refresh(share)
        assert share.views == 0 and "tier_list_link_opened" not in recorded
        other.get(made["path"], headers=PERSON)
    db_session.refresh(share)
    assert share.views == 1 and recorded.count("tier_list_link_opened") == 1


# ---------------------------------------------------------------- share card

def _png(width, height, colour=(220, 20, 20)):
    buffer = BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _tile_colour(png):
    with Image.open(BytesIO(png)) as card:
        x = tier_list_shares.CARD_PAD + tier_list_shares.CARD_LABEL + tier_list_shares.CARD_GAP + 25
        rows = tier_list_shares.CARD_H - tier_list_shares.CARD_TOP - tier_list_shares.CARD_BOTTOM
        row_h = (rows - 4 * 6) // 5
        y = tier_list_shares.CARD_TOP + (row_h - tier_list_shares.CARD_TILE_H) // 2 + 60
        return card.convert("RGB").getpixel((x, y))


def test_oversized_posters_get_a_text_tile_instead_of_being_decoded(monkeypatch):
    data = {"labels": {tier: tier for tier in tier_list.TIERS},
            "tiers": {"S": [{"title": "Dune", "image": "https://m.media-amazon.com/a.jpg"}], "A": [], "B": [], "C": [], "D": []}}
    normal = tier_list_shares.render_card("Mine", data, "someone", {("S", 0): _png(100, 150)})
    assert _tile_colour(normal) == (220, 20, 20)
    # A small file that would decode to more pixels than the limit is never converted.
    monkeypatch.setattr(tier_list_shares, "CARD_POSTER_PIXELS", 100 * 150 - 1)
    converted = []
    real_convert = Image.Image.convert
    monkeypatch.setattr(Image.Image, "convert", lambda self, *a, **k: converted.append(self.size) or real_convert(self, *a, **k))
    huge = tier_list_shares.render_card("Mine", data, "someone", {("S", 0): _png(100, 150)})
    assert _tile_colour(huge) == (49, 46, 129)
    assert (100, 150) not in converted


def test_a_card_never_takes_every_shared_image_slot(monkeypatch):
    monkeypatch.setattr(tier_list_router, "_card_fetch_slots", None)
    monkeypatch.setattr(tier_list_router, "_image_slots", None)
    monkeypatch.setattr(tier_list_router, "_image_cache_enabled", lambda: False)
    busy = {"now": 0, "most": 0}

    async def fetch(client, url):
        busy["now"] += 1
        busy["most"] = max(busy["most"], busy["now"])
        await asyncio.sleep(0.01)
        busy["now"] -= 1
        return "image/png", _png(10, 15)

    monkeypatch.setattr(tier_list_router, "_fetch_image", fetch)
    items = [{"title": f"T{n}", "image": f"https://m.media-amazon.com/{n}.jpg"} for n in range(12)]
    data = {"labels": {}, "tiers": {"S": items, "A": [], "B": [], "C": [], "D": []}}
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(external_api_client=object())))
    posters = asyncio.run(tier_list_router._card_posters(request, data))
    assert len(posters) == 12
    assert busy["most"] == tier_list_router.CARD_FETCH_SLOTS < tier_list_router.IMAGE_CONCURRENCY


# ---------------------------------------------------------------- check-in email

def test_due_members_check_libraries_in_a_fixed_number_of_queries(db_session):
    for number in range(12):
        user = member(db_session, f"away{number}", away_days=14)
        save(db_session, user, title=f"Film {number}")
    db_session.commit()
    due, statements = _count_sql(lambda: check_in.due_members(db_session, NOW))
    assert len(due) == 12
    library_reads = [sql for sql in statements if "FROM movies" in sql or "FROM podcasts" in sql]
    assert len(library_reads) == 2, len(library_reads)  # one per library, not two per library per member
    assert len(statements) <= 16, len(statements)


def test_something_to_ask_matches_the_titles_an_email_would_name(db_session):
    cases = {
        "unfinished": [dict(title="Dune")],
        "unrated": [dict(title="Dune", watched=True)],
        "rated": [dict(title="Dune", watched=True, rating=8)],
        "blank": [dict(title="   ")],
        "nothing": [],
    }
    users = {}
    for name, rows in cases.items():
        user = member(db_session, name, away_days=14)
        for fields in rows:
            save(db_session, user, **fields)
        users[name] = user
    pod_going = member(db_session, "podgoing", away_days=14)
    db_session.add(models.Podcast(title="Serial", user_id=pod_going.id, listened=False))
    pod_done = member(db_session, "poddone", away_days=14)
    db_session.add(models.Podcast(title="Serial", user_id=pod_done.id, listened=True))
    users.update(podgoing=pod_going, poddone=pod_done)
    db_session.commit()
    found = check_in.members_with_something_to_ask(db_session, [user.id for user in users.values()])
    for name, user in users.items():
        assert (user.id in found) == bool(check_in.candidates(db_session, user.id)), name
    assert found == {users["unfinished"].id, users["unrated"].id, users["poddone"].id}


def test_come_back_email_builder_keeps_its_docstring():
    assert comeback.build_email.__doc__.startswith("(subject, html, text)")
