"""Bug and speed fixes from the October 16 sweep of the features added since the last one."""
import asyncio
import random
from datetime import date, datetime, timedelta

import pytest

from app import comeback, models, pick, title_pages, title_search
from app.for_you import LibraryMatcher, _matches
from app.routers import tier_list as tier_list_router


def member(db, name, **extra):
    fields = {"is_active": True, "is_verified": True, **extra}
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", **fields)
    db.add(user)
    db.flush()
    return user


@pytest.fixture(autouse=True)
def fresh_index():
    title_search.clear_cache()
    yield
    title_search.clear_cache()


# ---------------------------------------------------------------- release matching

def test_library_matcher_finds_the_same_title_as_comparing_every_pair():
    words = ["the", "a", "dark", "knight", "rises", "dune", "part", "two", "Frieren:", "Beyond", "one", "piece", "!!", "2"]
    rng = random.Random(7)
    for _ in range(2000):
        library = [" ".join(rng.choice(words) for _ in range(rng.randint(1, 3))) for _ in range(rng.randint(0, 8))]
        names = [" ".join(rng.choice(words) for _ in range(rng.randint(0, 4))) for _ in range(rng.randint(1, 2))]
        expected = next((title for title in library if any(_matches(title, name) for name in names)), None)
        assert LibraryMatcher(library).find(names) == expected, (library, names)


def test_library_matcher_keeps_category_pairs_and_library_order():
    matcher = LibraryMatcher([("movies", "Dune Part Two"), ("movies", "Dune"), ("tv-shows", "Dune")])
    assert matcher.find(["Dune: Part Two"]) == ("movies", "Dune Part Two")
    assert matcher.find(["Dune Messiah"]) == ("movies", "Dune")
    assert matcher.find(["Dun"]) is None


# ---------------------------------------------------------------- search index

def test_search_index_failure_rolls_back_and_keeps_the_last_good_index(db_session, monkeypatch):
    ann = member(db_session, "ann")
    db_session.add(models.Movie(user_id=ann.id, title="Interstellar", director="Nolan", year=2014))
    db_session.commit()
    good = title_search.index(db_session)
    assert any(entry["title"] == "Interstellar" for entry in good)

    # Expire the cache and make the rebuild fail.
    title_search._cache["at"] -= title_search.CACHE_SECONDS + 1
    rolled_back = []
    monkeypatch.setattr(title_search, "build_index", lambda db: (_ for _ in ()).throw(RuntimeError("db down")))
    monkeypatch.setattr(db_session, "rollback", lambda: rolled_back.append(True))
    assert title_search.index(db_session) is good
    assert rolled_back == [True]
    # The next try comes after a short pause, not a whole cache window.
    assert title_search.CACHE_SECONDS - (title_search.time.monotonic() - title_search._cache["at"]) <= title_search.FAILURE_RETRY_SECONDS + 1


def test_expired_index_is_served_while_another_request_rebuilds_it(db_session, monkeypatch):
    stale = [{"kind": "movie", "title": "Old"}]
    title_search._cache.update(at=title_search.time.monotonic() - title_search.CACHE_SECONDS - 1, entries=stale)
    calls = []
    monkeypatch.setattr(title_search, "build_index", lambda db: calls.append(1) or [])
    assert title_search._build_lock.acquire(blocking=False)
    try:
        assert title_search.index(db_session) is stale
        assert calls == []
    finally:
        title_search._build_lock.release()
    assert title_search.index(db_session) == []
    assert calls == [1]


def test_pick_details_are_reused_for_the_same_index():
    index = []
    first = pick.title_details(index)
    assert pick.title_details(index) is first
    assert pick.title_details([]) is not first


# ---------------------------------------------------------------- title pages

def test_unknown_slug_scan_returns_matching_rows_only(db_session):
    ann, ben = member(db_session, "ann"), member(db_session, "ben")
    db_session.add_all([
        models.Movie(user_id=ann.id, title="Pokémon: The First Movie", director="Yuyama", year=1998),
        models.Movie(user_id=ben.id, title="Pokémon - The First Movie", director="Yuyama", year=1998),
        models.Movie(user_id=ben.id, title="Pokémon: The First Movie", director="Yuyama", year=1999),
        models.VideoGame(user_id=ann.id, title="Pokémon Red", release_date=date(1996, 2, 27)),
    ])
    db_session.commit()
    group = title_pages.find(db_session, "movie", "pokemon-the-first-movie-1998")
    assert group is not None and len(group.items) == 2
    assert {row.year for row in group.items} == {1998}
    game = title_pages.find(db_session, "game", "pokemon-red-1996")
    assert game is not None and game.items[0].title == "Pokémon Red"
    assert title_pages.find(db_session, "movie", "pokemon-the-first-movie-2001") is None


# ---------------------------------------------------------------- come-back email

def test_comeback_due_members_counts_unanswered_emails_per_member(db_session):
    now = datetime(2026, 10, 16, 12)
    old = now - timedelta(days=200)
    quiet = member(db_session, "quiet", created_at=old, last_login_at=old)
    nagged = member(db_session, "nagged", created_at=old, last_login_at=old)
    returned = member(db_session, "returned", created_at=old, last_login_at=now - timedelta(days=40))
    for user, days in ((nagged, 150), (nagged, 90), (returned, 150), (returned, 90)):
        db_session.add(models.EmailCampaignSend(campaign_key=f"comeback-{days}", user_id=user.id, status="sent",
                                                sent_at=now - timedelta(days=days)))
    db_session.commit()
    due = {user.username for user in comeback.due_members(db_session, now)}
    # Two unanswered emails stop them; coming back in between resets the count.
    assert due == {"quiet", "returned"}


# ---------------------------------------------------------------- tier list image proxy

class _SlowClient:
    def __init__(self):
        self.active = 0
        self.peak = 0

    def stream(self, method, url, headers=None):
        client = self

        class _Upstream:
            status_code = 200
            headers = {"content-type": "image/png"}

            async def __aenter__(self):
                client.active += 1
                client.peak = max(client.peak, client.active)
                await asyncio.sleep(0.01)
                return self

            async def __aexit__(self, *exc):
                client.active -= 1

            async def aiter_bytes(self):
                yield b"png"

        return _Upstream()


def test_image_proxy_limits_parallel_fetches(monkeypatch):
    client = _SlowClient()

    class _State:
        external_api_client = client

    class _App:
        state = _State()

    class _Request:
        app = _App()

    async def run():
        monkeypatch.setattr(tier_list_router, "_image_slots", asyncio.Semaphore(tier_list_router.IMAGE_CONCURRENCY))
        url = "https://m.media-amazon.com/images/poster.jpg"
        responses = await asyncio.gather(*(tier_list_router.tier_list_image(_Request(), url) for _ in range(20)))
        assert all(response.body == b"png" for response in responses)

    asyncio.run(run())
    assert client.peak <= tier_list_router.IMAGE_CONCURRENCY
