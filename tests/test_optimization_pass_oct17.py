"""October speed pass: the faster paths return exactly what the slower ones did."""
import asyncio
from contextlib import contextmanager

from sqlalchemy import event, inspect

from app import crud, models, review_quality, taste_match, title_pages
from app.routers import seo, tier_list as tier_list_router
from tests.test_title_pages import add_movie, member

GOOD_REVIEW = ("The pacing is patient and the final hour rewards it. Every performance feels lived in, and the score "
               "carries the quiet scenes without ever pushing. I left thinking about the ending for days, which says a "
               "lot about how carefully the story sets it up. Worth seeing on the biggest screen you can find.")


@contextmanager
def count_queries(db):
    statements = []

    def record(conn, cursor, statement, *args):
        statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)


def _me(db):
    return db.query(models.User).filter_by(username="testuser").one()


# ---------------------------------------------------------------- title pages / sitemap

def test_find_many_matches_find_for_every_slug(db_session):
    a, b, c = member(db_session, "fa"), member(db_session, "fb"), member(db_session, "fc")
    add_movie(db_session, a, "Interstellar", 2014)
    add_movie(db_session, b, "interstellar", 2014)
    add_movie(db_session, c, "Interstellar", 1999)
    add_movie(db_session, a, "Pokémon: The First Movie", 1998)
    add_movie(db_session, b, "Up", None)
    add_movie(db_session, c, "Up", 0)
    add_movie(db_session, a, "1917", 2019)
    db_session.commit()
    slugs = ["interstellar-2014", "interstellar-1999", "interstellar", "pokemon-the-first-movie-1998", "up",
             "1917-2019", "1917", "missing-2001", "BAD SLUG", ""]
    many = title_pages.find_many(db_session, "movie", slugs)
    for slug in slugs:
        expected = title_pages.find(db_session, "movie", slug)
        found = many.get(slug)
        if expected is None:
            assert found is None, slug
        else:
            assert (found.title, found.year, found.normalized, [i.id for i in found.items]) == \
                   (expected.title, expected.year, expected.normalized, sorted(i.id for i in expected.items)), slug


def test_find_many_skips_private_shelves(db_session):
    shy = member(db_session, "shy")
    shy.movies_private = True
    add_movie(db_session, shy, "Hidden Gem", 2010)
    db_session.commit()
    assert title_pages.find_many(db_session, "movie", ["hidden-gem-2010"]) == {}
    assert title_pages.find(db_session, "movie", "hidden-gem-2010") is None


def test_summary_without_page_sections_keeps_every_count(db_session):
    a, b = member(db_session, "sa"), member(db_session, "sb")
    add_movie(db_session, a, "Arrival", 2016, rating=9, watched=True, review=GOOD_REVIEW, review_public=True)
    add_movie(db_session, b, "Arrival", 2016, rating=8)
    db_session.commit()
    group = title_pages.find(db_session, "movie", "arrival-2016")
    full = title_pages.summarize(db_session, group)
    light = title_pages.summarize(db_session, group, page_sections=False)
    assert light["related"] == [] and light["collections"] == []
    assert {k: v for k, v in light.items() if k not in ("related", "collections")} == \
           {k: v for k, v in full.items() if k not in ("related", "collections")}
    assert title_pages.is_indexable(light, None) == title_pages.is_indexable(full, None) is True


def test_sitemap_member_entries_are_reused_while_fresh(client, monkeypatch):
    calls = []

    def build(db):
        calls.append(1)
        return [f"<url><loc>build-{len(calls)}</loc></url>"]

    monkeypatch.setattr(seo, "_database_parts", build)
    monkeypatch.setattr(seo, "_sitemap_cache_enabled", lambda: True)
    monkeypatch.setattr(seo, "_sitemap_cache", {"at": 0.0, "parts": None})
    first = client.get("/sitemap.xml").text
    second = client.get("/sitemap.xml").text
    assert "build-1" in first and "build-1" in second and len(calls) == 1
    seo._sitemap_cache["at"] -= seo.SITEMAP_CACHE_SECONDS + 1
    assert "build-2" in client.get("/sitemap.xml").text


# ---------------------------------------------------------------- review quality

def test_review_quality_reuses_results_without_sharing_checks():
    review_quality._evaluated.clear()
    first = review_quality.evaluate_public_review(GOOD_REVIEW, 80, 240)
    first.checks["safe_to_share"] = False  # a caller editing its copy
    second = review_quality.evaluate_public_review("  " + GOOD_REVIEW + "\n", 80, 240)
    assert second == review_quality._evaluate(GOOD_REVIEW, 80, 240)
    assert second.checks["safe_to_share"] is True
    assert review_quality.evaluate_public_review(GOOD_REVIEW, 80, 2000).search_ready is False
    assert review_quality.evaluate_public_review(None) == review_quality._evaluate("", 80, 240)


def test_review_quality_memory_is_bounded(monkeypatch):
    review_quality._evaluated.clear()
    monkeypatch.setattr(review_quality, "_EVALUATED_MAX", 3)
    for n in range(10):
        review_quality.evaluate_public_review(f"review number {n}")
    assert len(review_quality._evaluated) == 3


# ---------------------------------------------------------------- friends and Taste Match

def test_taste_match_scores_read_libraries_in_a_fixed_number_of_queries(authenticated_client, db_session):
    me = _me(db_session)
    add_movie(db_session, me, "Heat", 1995, rating=9)
    add_movie(db_session, me, "Alien", 1979, rating=8)
    add_movie(db_session, me, "Brazil", 1985, rating=7)
    friends = []
    for n in range(8):
        pal = member(db_session, f"pal{n}")
        for title, year, rating in (("Heat", 1995, 9 - n % 3), ("Alien", 1979, 8), ("Brazil", 1985, 3 + n % 5)):
            add_movie(db_session, pal, title, year, rating=rating, review="Long private notes " * 40)
        if n % 2:
            pal.books_private = True
        crud.create_friendship(db_session, me.id, pal.id)
        friends.append(pal)
    db_session.commit()
    expected = [{"friend_id": pal.id, **{k: v for k, v in taste_match.compare(
        taste_match.library(db_session, me.id, taste_match.LIBRARY),
        taste_match.library(db_session, pal.id, taste_match.shared_categories(pal)),
        taste_match.shared_categories(pal)).items() if k in ("score", "tier", "shared_count")}} for pal in friends]
    with count_queries(db_session) as statements:
        scores = taste_match.friend_scores(db_session, me, crud.get_friends(db_session, me.id))
    assert sorted(scores, key=lambda r: r["friend_id"]) == sorted(expected, key=lambda r: r["friend_id"])
    assert len(statements) <= 2 + 2 * len(taste_match.LIBRARY)  # not one query per friend
    response = authenticated_client.get("/api/taste-match/friends")
    assert response.status_code == 200 and len(response.json()["friends"]) == 8


def test_get_friends_keeps_order_in_one_lookup(db_session):
    me = member(db_session, "hub")
    pals = [member(db_session, f"p{n}") for n in range(5)]
    for pal in reversed(pals):
        crud.create_friendship(db_session, me.id, pal.id)
    db_session.commit()
    order = [f.user2_id if f.user1_id == me.id else f.user1_id
             for f in db_session.query(models.Friendship).filter(
                 (models.Friendship.user1_id == me.id) | (models.Friendship.user2_id == me.id))]
    with count_queries(db_session) as statements:
        friends = crud.get_friends(db_session, me.id)
    assert [f.id for f in friends] == order and len(statements) == 2


def test_profile_picture_bytes_load_only_when_served(authenticated_client, db_session):
    me = _me(db_session)
    me.profile_picture_data = b"RIFF0000WEBPpicture"
    me.profile_picture_mime_type = "image/webp"
    me.profile_picture_url = f"/profile-pictures/{me.id}"
    db_session.commit()
    db_session.expire_all()
    loaded = db_session.query(models.User).filter_by(id=me.id).one()
    assert "profile_picture_data" in inspect(loaded).unloaded
    first = authenticated_client.get(f"/profile-pictures/{me.id}")
    assert first.status_code == 200 and first.content == b"RIFF0000WEBPpicture"
    assert first.headers["cache-control"] == "private, no-cache"
    again = authenticated_client.get(f"/profile-pictures/{me.id}", headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304 and again.content == b""
    me.profile_picture_data = b"RIFF0000WEBPnew"
    db_session.commit()
    changed = authenticated_client.get(f"/profile-pictures/{me.id}", headers={"If-None-Match": first.headers["etag"]})
    assert changed.status_code == 200 and changed.content == b"RIFF0000WEBPnew"


def test_profile_picture_etag_never_bypasses_privacy(client, db_session):
    owner = member(db_session, "privatepic")
    owner.profile_picture_data = b"secret"
    db_session.commit()
    import hashlib
    etag = '"' + hashlib.blake2b(b"secret", digest_size=16).hexdigest() + '"'
    assert client.get(f"/profile-pictures/{owner.id}", headers={"If-None-Match": etag}).status_code == 404


def test_starter_picks_skip_ranking_once_the_goal_is_reached(authenticated_client, db_session):
    me = _me(db_session)
    for n in range(5):
        add_movie(db_session, me, f"Mine {n}", 2000 + n)
    db_session.commit()
    with count_queries(db_session) as statements:
        data = authenticated_client.get("/api/for-you/starter-picks").json()
    assert data == {"library_total": 5, "goal": 5, "popular": [], "upcoming": []}
    assert not any("count(DISTINCT" in s or "count(distinct" in s for s in statements)


# ---------------------------------------------------------------- tier list image proxy

class _Request:
    def __init__(self, client, host):
        self.app = type("App", (), {"state": type("State", (), {"external_api_client": client})()})()
        self.client = type("Client", (), {"host": host})()
        self.headers = {}


class _CountingClient:
    def __init__(self):
        self.active = {}
        self.peak = {}
        self.calls = 0

    def stream(self, method, url, headers=None):
        client, host = self, url.split("/")[-1].split("-")[0]

        class _Upstream:
            status_code = 200
            headers = {"content-type": "image/png"}

            async def __aenter__(self):
                client.calls += 1
                client.active[host] = client.active.get(host, 0) + 1
                client.peak[host] = max(client.peak.get(host, 0), client.active[host])
                await asyncio.sleep(0.01)
                return self

            async def __aexit__(self, *exc):
                client.active[host] -= 1

            async def aiter_bytes(self):
                yield b"png"

        return _Upstream()


def test_image_proxy_caps_each_visitor_and_reuses_posters(monkeypatch):
    upstream = _CountingClient()
    monkeypatch.setattr(tier_list_router, "_image_cache_enabled", lambda: True)
    monkeypatch.setattr(tier_list_router, "_image_cache", type(tier_list_router._image_cache)())
    monkeypatch.setattr(tier_list_router, "_image_cache_size", 0)

    async def run():
        monkeypatch.setattr(tier_list_router, "_image_slots", asyncio.Semaphore(tier_list_router.IMAGE_CONCURRENCY))
        greedy = [tier_list_router.tier_list_image(_Request(upstream, "1.1.1.1"),
                                                   f"https://m.media-amazon.com/images/greedy-{n}.jpg") for n in range(12)]
        polite = [tier_list_router.tier_list_image(_Request(upstream, "2.2.2.2"),
                                                   f"https://m.media-amazon.com/images/polite-{n}.jpg") for n in range(2)]
        responses = await asyncio.gather(*greedy, *polite)
        assert all(r.body == b"png" for r in responses)
        before = upstream.calls
        again = await tier_list_router.tier_list_image(_Request(upstream, "3.3.3.3"),
                                                       "https://m.media-amazon.com/images/polite-0.jpg")
        assert again.body == b"png" and again.media_type == "image/png" and upstream.calls == before

    asyncio.run(run())
    assert max(upstream.peak.values()) <= tier_list_router.IMAGE_SLOTS_PER_CLIENT
    assert tier_list_router._client_slots == {}
