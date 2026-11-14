"""Awards season: the calendar and show pages, ballots, the lock, results and scores, sharing and the library ties."""
import json
from datetime import datetime

import pytest

from app import awards, awards_data, models, site_traffic, title_pages
from app.routers import awards as awards_router

NOW = datetime(2026, 11, 20, 12, 0)
SHOW = "test-awards-2026"
CHROME = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


def _demo_show() -> dict:
    return {
        "name": "Test Awards 2026", "short": "The Test Awards", "format": "Video games",
        "title": "Test Awards 2026: date, nominees and your ballot",
        "search_title": "Test Awards 2026", "description": "A show used by the tests.",
        "lead": "A show used by the tests.", "published": "2026-11-12", "reviewed": "2026-11-12",
        "ceremony_day": "2026-12-10", "ceremony_at": "2026-12-11T00:30:00",
        "lock_label": "Thursday, December 10 at 4:30 p.m. Pacific", "watch": "Free streams",
        "nominees_day": "2026-11-16", "nominees_label": "November 16, 2026",
        "nominees_note": "Nominees came out on November 16.",
        "dates": (("Ceremony", "Thursday, December 10, 2026"),),
        "sections": (("chosen", "How the winners are chosen", ("A jury votes.",)),),
        "categories": [
            {"name": "Game of the Year", "nominees": [
                {"name": "Hades II", "detail": "Supergiant Games", "kind": "game", "year": 2025},
                {"name": "Hollow Knight: Silksong", "detail": "Team Cherry", "kind": "game", "year": 2025},
                {"name": "Donkey Kong Bananza", "detail": "Nintendo", "kind": "game", "year": 2025},
            ]},
            {"name": "Best Performance", "nominees": [
                {"name": "Jennifer English", "detail": "Maelle in Clair Obscur: Expedition 33",
                 "kind": "game", "title": "Clair Obscur: Expedition 33", "year": 2025},
                {"name": "Troy Baker", "detail": "Indiana Jones and the Great Circle"},
            ]},
            {"name": "Best Esports Team", "nominees": [
                {"name": "Team Vitality", "detail": "Counter-Strike 2"},
                {"name": "Gen.G", "detail": "League of Legends"},
            ]},
        ],
        "last_year": {"heading": "Last year", "intro": ("It happened.",), "winners": (
            ("Game of the Year", "Astro Bot", "Team Asobi", {"kind": "game", "title": "Astro Bot", "year": 2024}),
            ("Best Esports Team", "T1", "League of Legends", None),
        )},
        "faq": (("When is it?", "December 10."),),
        "sources": (("Example", "https://example.com/"),),
    }


@pytest.fixture
def demo(monkeypatch):
    """A show with nominees, three weeks before its ceremony."""
    monkeypatch.setitem(awards_data.SHOWS, SHOW, _demo_show())
    monkeypatch.setattr(awards, "_now", lambda: NOW)
    return awards_data.SHOWS[SHOW]


def _user(db_session, username="testuser"):
    return db_session.query(models.User).filter(models.User.username == username).one()


def _other(db_session, name, **flags):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=True, **flags)
    db_session.add(user)
    db_session.flush()
    return user


def _ballot(db_session, user, picks, **fields):
    row = models.AwardBallot(user_id=user.id, show=SHOW, picks=json.dumps(picks), **fields)
    db_session.add(row)
    db_session.commit()
    return row


def _lock(monkeypatch):
    monkeypatch.setattr(awards, "_now", lambda: datetime(2026, 12, 11, 1, 0))


# ---------------------------------------------------------------- the data

def test_every_show_has_what_its_page_needs():
    assert set(awards_data.ORDER) == set(awards_data.SHOWS)
    stamps = []
    for slug, show in awards.ordered():
        assert title_pages.slugify(slug) == slug and len(slug) <= 60
        for field in ("name", "short", "format", "title", "search_title", "description", "lead", "lock_label",
                      "watch", "nominees_label", "nominees_note"):
            assert show[field].strip(), (slug, field)
        assert 50 <= len(show["description"]) <= 200, slug
        at = awards.ceremony_at(show)
        day = datetime.fromisoformat(show["ceremony_day"])
        # Picks lock on the day of the ceremony, somewhere in the Americas' afternoon or evening (UTC).
        assert day <= at <= day.replace(hour=23, minute=59) + (datetime(2026, 1, 2) - datetime(2026, 1, 1)), slug
        stamps.append(at)
        datetime.fromisoformat(show["published"]), datetime.fromisoformat(show["reviewed"])
        assert len(show["dates"]) >= 4 and len(show["sections"]) >= 2 and len(show["faq"]) >= 3, slug
        assert sum(len(text.split()) for _, _, paragraphs in show["sections"] for text in paragraphs) >= 90, slug
        assert all(url.startswith("https://") for _, url in show["sources"]), slug
        keys = [category["key"] for category in awards.categories(show)]
        assert len(keys) == len(set(keys)), slug
        for category in awards.categories(show):
            names = [nominee["key"] for nominee in category["nominees"]]
            assert len(names) >= 2 and len(names) == len(set(names)), (slug, category["name"])
        for row in awards.last_year_winners(show):
            assert row["category"] and row["name"], slug
    assert stamps == sorted(stamps)


def test_states(demo):
    assert awards.state(demo, 0, NOW) == "open" and awards.is_open(demo, NOW)
    assert awards.days_left(demo, NOW) == 20
    assert awards.state(demo, 0, datetime(2026, 12, 11, 0, 30)) == "locked"
    assert awards.state(demo, 2, datetime(2026, 12, 11, 2, 0)) == "locked"
    assert awards.state(demo, 3, datetime(2026, 12, 11, 4, 0)) == "results"
    empty = dict(demo, categories=[])
    assert awards.state(empty, 0, NOW) == "coming" and not awards.is_open(empty, NOW)
    assert awards.score({"a": "x", "b": "y", "c": "z"}, {"a": "x", "b": "n"}) == {"correct": 1, "judged": 2, "decided": 2}
    assert awards.agreement({"a": "x", "b": "y"}, {"a": "x", "b": "z", "c": "q"}) == {"both": 2, "same": 1}


# ---------------------------------------------------------------- public pages

def test_calendar_page(client):
    response = client.get("/awards")
    assert response.status_code == 200
    html = response.text
    for slug, show in awards.ordered():
        assert f'href="/awards/{slug}"' in html and show["name"] in html
    assert "Crunchyroll Anime Awards 2027" in html and "Not announced" in html
    assert 'content="index, follow' in html and '"@type": "FAQPage"' in html
    assert '<link rel="canonical" href="https://omnitrackr.xyz/awards">' in html
    assert "/static/ad-loader.js" in html
    assert "private" in response.headers["cache-control"]


def test_show_page_before_nominees(client):
    response = client.get("/awards/the-game-awards-2026")
    assert response.status_code == 200
    html = response.text
    assert "The ballot opens when the nominees are announced" in html
    assert "Make a free account to get a reminder" in html
    assert "/?next=%2Fawards%2Fthe-game-awards-2026%23ballot#landing-auth" in html
    assert "Clair Obscur: Expedition 33" in html and "Key dates" in html
    assert 'content="index, follow' in html
    # Nothing to pick yet, and visitors get no library buttons.
    assert 'type="radio"' not in html and "data-award-add" not in html
    assert client.get("/awards/not-a-show").status_code == 404
    assert client.get("/api/awards/the-game-awards-2026").status_code == 401


def test_open_ballot_for_a_visitor(client, demo):
    html = client.get(f"/awards/{SHOW}").text
    assert "BALLOT OPEN · LOCKS IN 20 DAYS" in html
    assert html.count('type="radio"') == 7 and "checked" not in html.split('data-award-form')[1].split("</form>")[0]
    assert 'name="game-of-the-year" value="hades-ii"' in html
    assert "Save my ballot, free" in html and "0 of 3 picked" in html
    assert "data-award-add" not in html and "data-award-winner" not in html
    assert "% of ballots" not in html


def test_guides_index_and_sitemap_list_the_pages(client, db_session):
    sitemap = client.get("/sitemap.xml").text
    assert "<loc>https://omnitrackr.xyz/awards</loc>" in sitemap
    assert "<loc>https://omnitrackr.xyz/awards/oscars-2027</loc>" in sitemap
    assert "/ballot/" not in sitemap
    from app import editorial_index
    hrefs = {entry["href"] for entry in editorial_index.entries()}
    assert "/awards" in hrefs and "/awards/grammys-2027" in hrefs


def test_sign_in_returns_to_the_ballot_and_ads_may_load():
    from pathlib import Path
    static = Path(__file__).parents[1] / "app" / "static"
    assert r"/^\/awards\/[a-z0-9-]{1,60}#ballot$/" in (static / "auth.js").read_text(encoding="utf-8")
    assert r"/^\/awards(\/[a-z0-9-]{1,60})?$/" in (static / "ad-loader.js").read_text(encoding="utf-8")
    assert site_traffic.clean_path("/ballot/AbCdEf123456_-xy") == "/ballot/(private link)"
    assert site_traffic.clean_path("/awards/oscars-2027") == "/awards/oscars-2027"


# ---------------------------------------------------------------- reminders

def test_member_asks_to_hear_when_the_ballot_opens(authenticated_client, db_session, monkeypatch):
    slug = "the-game-awards-2026"
    page = authenticated_client.get(f"/awards/{slug}").text
    assert "Tell me when the ballot opens" in page and "/static/ad-loader.js" not in page
    state = authenticated_client.put(f"/api/awards/{slug}/follow").json()
    assert state["following"] and state["state"] == "coming" and state["picked"] == 0
    assert "You're on the list." in authenticated_client.get(f"/awards/{slug}").text
    # Nothing goes out while there are no nominees.
    assert awards.send_notices(db_session) == {"opened": 0, "results": 0}
    # The nominees land: one note, once.
    show = dict(awards_data.SHOWS[slug], categories=_demo_show()["categories"])
    monkeypatch.setitem(awards_data.SHOWS, slug, show)
    monkeypatch.setattr(awards, "_now", lambda: NOW)
    assert awards.send_notices(db_session)["opened"] == 1
    assert awards.send_notices(db_session)["opened"] == 0
    note = db_session.query(models.Notification).filter_by(type="awards_ballot_open").one()
    assert note.link == f"/awards/{slug}#ballot" and "The Game Awards 2026 nominees are in" in note.message
    # "Don't tell me" removes the row.
    assert authenticated_client.delete(f"/api/awards/{slug}/ballot").status_code == 200
    assert db_session.query(models.AwardBallot).count() == 0


def test_no_opening_note_for_someone_who_already_picked(authenticated_client, db_session, demo):
    authenticated_client.put(f"/api/awards/{SHOW}/ballot", json={"picks": {"game-of-the-year": "hades-ii"}})
    assert awards.send_notices(db_session) == {"opened": 0, "results": 0}
    assert db_session.query(models.Notification).filter_by(type="awards_ballot_open").count() == 0


# ---------------------------------------------------------------- picking

def test_picks_save_one_click_at_a_time(authenticated_client, db_session, demo):
    url = f"/api/awards/{SHOW}/ballot"
    first = authenticated_client.put(url, json={"picks": {"game-of-the-year": "hades-ii"}})
    assert first.status_code == 200 and first.json()["picks"] == {"game-of-the-year": "hades-ii"}
    assert first.headers["cache-control"] == "private, no-store"
    second = authenticated_client.put(url, json={"picks": {"best-esports-team": "gen-g"}}).json()
    assert second["picks"] == {"game-of-the-year": "hades-ii", "best-esports-team": "gen-g"} and second["picked"] == 2
    changed = authenticated_client.put(url, json={"picks": {"game-of-the-year": "donkey-kong-bananza", "best-esports-team": None}}).json()
    assert changed["picks"] == {"game-of-the-year": "donkey-kong-bananza"}
    assert db_session.query(models.AwardBallot).count() == 1
    page = authenticated_client.get(f"/awards/{SHOW}").text
    assert 'value="donkey-kong-bananza" checked' in page and "1 of 3 picked" in page
    assert "Share your ballot" in page and "Clear my ballot" in page
    state = authenticated_client.get(f"/api/awards/{SHOW}").json()
    assert state["state"] == "open" and state["total"] == 3 and state["days_left"] == 20


def test_bad_picks_are_refused(authenticated_client, db_session, demo):
    url = f"/api/awards/{SHOW}/ballot"
    assert authenticated_client.put(url, json={"picks": {"best-film": "x"}}).status_code == 422
    assert authenticated_client.put(url, json={"picks": {"game-of-the-year": "tetris"}}).status_code == 422
    assert authenticated_client.put(url, json={"picks": {}}).status_code == 422
    assert authenticated_client.put("/api/awards/not-a-show/ballot", json={"picks": {"a": "b"}}).status_code == 404
    # A show without nominees has nothing to pick.
    assert authenticated_client.put("/api/awards/oscars-2027/ballot", json={"picks": {"a": "b"}}).status_code == 422
    assert db_session.query(models.AwardBallot).count() == 0


def test_picks_lock_when_the_show_starts(authenticated_client, db_session, demo, monkeypatch):
    url = f"/api/awards/{SHOW}/ballot"
    assert authenticated_client.put(url, json={"picks": {"game-of-the-year": "hades-ii"}}).status_code == 200
    _lock(monkeypatch)
    late = authenticated_client.put(url, json={"picks": {"game-of-the-year": "donkey-kong-bananza"}})
    assert late.status_code == 409 and "locked" in late.json()["detail"]
    assert authenticated_client.get(f"/api/awards/{SHOW}").json()["picks"] == {"game-of-the-year": "hades-ii"}
    page = authenticated_client.get(f"/awards/{SHOW}").text
    assert "PICKS LOCKED" in page and 'value="hades-ii" checked disabled' in page
    assert "Clear my ballot" not in page and "data-award-clear" not in page


def test_a_removed_nominee_drops_out_of_old_ballots(db_session, demo):
    user = _other(db_session, "robin")
    row = _ballot(db_session, user, {"game-of-the-year": "gone-game", "best-esports-team": "gen-g", "old-category": "x"})
    assert awards.picks_of(row, demo) == {"best-esports-team": "gen-g"}
    row.picks = "not json"
    assert awards.picks_of(row, demo) == {}


# ---------------------------------------------------------------- winners and scores

def test_only_the_site_owner_enters_winners(authenticated_client, db_session, demo, monkeypatch):
    url = f"/api/awards/{SHOW}/results"
    body = {"category": "game-of-the-year", "nominee": "hades-ii"}
    monkeypatch.delenv("ADMIN_USERNAMES", raising=False)
    monkeypatch.delenv("COLLECTION_MODERATOR_USERNAMES", raising=False)
    assert authenticated_client.put(url, json=body).status_code == 403
    assert "data-award-winner" not in authenticated_client.get(f"/awards/{SHOW}").text
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser")
    assert "Mark winner" in authenticated_client.get(f"/awards/{SHOW}").text
    assert authenticated_client.put(url, json=body).json() == {"results": {"game-of-the-year": "hades-ii"}}
    # Marking again changes the same row; null undoes it.
    body["nominee"] = "donkey-kong-bananza"
    assert authenticated_client.put(url, json=body).json()["results"] == {"game-of-the-year": "donkey-kong-bananza"}
    assert db_session.query(models.AwardResult).count() == 1
    assert authenticated_client.put(url, json={"category": "game-of-the-year", "nominee": "tetris"}).status_code == 422
    assert authenticated_client.put(url, json={"category": "nope", "nominee": "hades-ii"}).status_code == 422
    assert authenticated_client.put(url, json={"category": "game-of-the-year", "nominee": None}).json() == {"results": {}}


def test_a_winner_in_the_data_wins_over_an_entered_one(db_session, demo):
    awards.set_result(db_session, SHOW, "game-of-the-year", "hades-ii")
    demo["categories"][0]["winner"] = "hollow-knight-silksong"
    assert awards.results(db_session, SHOW) == {"game-of-the-year": "hollow-knight-silksong"}


def test_score_and_the_winners_note(authenticated_client, db_session, demo, monkeypatch):
    authenticated_client.put(f"/api/awards/{SHOW}/ballot",
                             json={"picks": {"game-of-the-year": "hades-ii", "best-performance": "troy-baker"}})
    skipper = _other(db_session, "skipper")
    _ballot(db_session, skipper, {})
    _lock(monkeypatch)
    awards.set_result(db_session, SHOW, "game-of-the-year", "hades-ii")
    state = authenticated_client.get(f"/api/awards/{SHOW}").json()
    assert state["state"] == "locked" and state["score"] == {"correct": 1, "judged": 1, "decided": 1}
    page = authenticated_client.get(f"/awards/{SHOW}").text
    assert "You called 1 of 1 so far. 1 of 3 winners are in." in page and "You called it: Hades II." in page
    assert awards.send_notices(db_session)["results"] == 0  # not every category has a winner yet
    awards.set_result(db_session, SHOW, "best-performance", "jennifer-english")
    awards.set_result(db_session, SHOW, "best-esports-team", "gen-g")
    state = authenticated_client.get(f"/api/awards/{SHOW}").json()
    assert state["state"] == "results" and state["score"] == {"correct": 1, "judged": 2, "decided": 3}
    page = authenticated_client.get(f"/awards/{SHOW}").text
    assert "THE WINNERS" in page and "You called 1 of 2." in page and "Winner: Jennifer English." in page
    # One note for the member who picked, none for the empty ballot, and never twice.
    assert awards.send_notices(db_session)["results"] == 1
    assert awards.send_notices(db_session)["results"] == 0
    note = db_session.query(models.Notification).filter_by(type="awards_results").one()
    assert note.user_id == _user(db_session).id and "You called 1 of 2" in note.message


# ---------------------------------------------------------------- how members voted

def test_member_percentages_show_only_after_the_lock_and_above_the_floor(client, db_session, demo, monkeypatch):
    for index in range(awards.MIN_PUBLIC_BALLOTS):
        user = _other(db_session, f"voter{index}")
        _ballot(db_session, user, {"game-of-the-year": "hades-ii" if index < 4 else "donkey-kong-bananza",
                                   **({"best-esports-team": "gen-g"} if index == 0 else {})})
    gone = _other(db_session, "gone", is_active=False)
    _ballot(db_session, gone, {"game-of-the-year": "donkey-kong-bananza"})
    before = awards.tallies(db_session, SHOW)
    assert before == {"ballots": 5, "show": False, "categories": {}}
    assert "% of ballots" not in client.get(f"/awards/{SHOW}").text
    _lock(monkeypatch)
    after = awards.tallies(db_session, SHOW)
    assert after["show"] and after["categories"] == {
        "game-of-the-year": {"hades-ii": 80, "hollow-knight-silksong": 0, "donkey-kong-bananza": 20}}
    html = client.get(f"/awards/{SHOW}").text
    assert "80% of ballots" in html and "0% of ballots" in html and "5 ballots filled in" in html
    # One fewer ballot and nothing is shown.
    db_session.query(models.AwardBallot).filter_by(user_id=_user(db_session, "voter0").id).delete()
    db_session.commit()
    assert not awards.tallies(db_session, SHOW)["show"]


# ---------------------------------------------------------------- sharing

def test_share_link_page_and_card(authenticated_client, client, db_session, demo):
    assert authenticated_client.put(f"/api/awards/{SHOW}/share").status_code == 404  # nothing picked yet
    authenticated_client.put(f"/api/awards/{SHOW}/ballot", json={"picks": {"game-of-the-year": "hades-ii"}})
    shared = authenticated_client.put(f"/api/awards/{SHOW}/share").json()
    assert shared["shared"] and shared["url"].startswith("https://omnitrackr.xyz/ballot/")
    again = authenticated_client.put(f"/api/awards/{SHOW}/share").json()
    assert again["url"] == shared["url"]
    path = shared["url"].replace("https://omnitrackr.xyz", "")
    authenticated_client.headers = {}
    authenticated_client.cookies.clear()
    response = client.get(path, headers=CHROME)
    assert response.status_code == 200 and response.headers["x-robots-tag"] == "noindex, follow"
    html = response.text
    assert "testuser&#x27;s Test Awards 2026 ballot" in html and "Hades II" in html and "Game of the Year" in html
    assert "1 of 3 categories picked" in html and f'{path}/card.png' in html and "Fill in your own ballot" in html
    card = client.get(f"{path}/card.png")
    assert card.status_code == 200 and card.headers["content-type"] == "image/png" and card.content[:4] == b"\x89PNG"
    assert client.get("/ballot/not-a-real-token").status_code == 404
    assert client.get("/ballot/" + "x" * 40).status_code == 404


def test_shared_ballot_ends_with_sharing_or_the_account(authenticated_client, db_session, demo):
    authenticated_client.put(f"/api/awards/{SHOW}/ballot", json={"picks": {"game-of-the-year": "hades-ii"}})
    path = authenticated_client.put(f"/api/awards/{SHOW}/share").json()["url"].replace("https://omnitrackr.xyz", "")
    assert authenticated_client.get(path).status_code == 200
    user = _user(db_session)
    user.is_active = False
    db_session.commit()
    assert awards.find_shared(db_session, path.rsplit("/", 1)[1]) is None
    user.is_active = True
    db_session.commit()
    assert authenticated_client.delete(f"/api/awards/{SHOW}/share").json()["shared"] is False
    assert authenticated_client.get(path).status_code == 404
    assert authenticated_client.get(f"{path}/card.png").status_code == 404


def test_shared_ballot_shows_the_score_and_how_you_compare(authenticated_client, db_session, demo, monkeypatch):
    robin = _other(db_session, "robin")
    _ballot(db_session, robin, {"game-of-the-year": "hades-ii", "best-esports-team": "gen-g"}, share_token="robinsballot1234")
    authenticated_client.put(f"/api/awards/{SHOW}/ballot",
                             json={"picks": {"game-of-the-year": "hades-ii", "best-esports-team": "team-vitality"}})
    html = authenticated_client.get("/ballot/robinsballot1234").text
    assert "You and robin agree on <strong>1 of 2</strong>" in html
    _lock(monkeypatch)
    awards.set_result(db_session, SHOW, "game-of-the-year", "hades-ii")
    awards.set_result(db_session, SHOW, "best-esports-team", "team-vitality")
    html = authenticated_client.get("/ballot/robinsballot1234").text
    assert "Called 1 of 2 so far, with 2 of 3 winners in." in html
    assert "Called it ✓" in html and "Missed" in html and "See every winner" in html
    lines = awards_router._shared_lines(demo, {"game-of-the-year": "hades-ii"}, {"game-of-the-year": "hades-ii"})
    assert lines == [{"category": "Game of the Year", "pick": "Hades II", "result": "hit"}]
    png = awards_router.render_ballot_card("robin", "Test Awards 2026", lines, {"correct": 1, "judged": 1, "decided": 1}, 9)
    assert png[:4] == b"\x89PNG"


# ---------------------------------------------------------------- library

def test_nominees_you_track_are_marked_and_the_rest_can_be_added(authenticated_client, db_session, demo):
    user = _user(db_session)
    db_session.add_all([
        models.VideoGame(user_id=user.id, title="hades ii", release_date=datetime(2025, 9, 25), played=True),
        models.VideoGame(user_id=user.id, title="Astro Bot", release_date=datetime(2024, 9, 6), played=False),
    ])
    db_session.commit()
    page = authenticated_client.get(f"/awards/{SHOW}").text
    assert "Played ✓" in page and "In your library ✓" in page
    assert 'data-award-add="game/hollow-knight-silksong-2025"' in page
    assert 'data-award-add="game/hades-ii-2025"' not in page and 'data-award-add="game/astro-bot-2024"' not in page
    # The performer's game can be added too; a team has nothing to add.
    assert 'data-award-add="game/clair-obscur-expedition-33-2025"' in page
    added = authenticated_client.post(f"/api/awards/{SHOW}/add", json={"id": "game/hollow-knight-silksong-2025"})
    assert added.status_code == 200 and added.json()["state"] == "created"
    game = db_session.query(models.VideoGame).filter_by(user_id=user.id, title="Hollow Knight: Silksong").one()
    assert game.played is not True and game.release_date.year == 2025
    assert added.json()["library_url"] == f"/?library_category=video-games&library_item={game.id}"
    # Adding a title already there changes nothing.
    existing = authenticated_client.post(f"/api/awards/{SHOW}/add", json={"id": "game/hades-ii-2025"}).json()
    assert existing["state"] == "existing"
    assert db_session.query(models.VideoGame).filter_by(user_id=user.id).count() == 3
    assert db_session.query(models.VideoGame).filter_by(user_id=user.id, played=True).count() == 1
    assert authenticated_client.post(f"/api/awards/{SHOW}/add", json={"id": "game/not-on-the-page"}).status_code == 404


def test_last_years_winners_work_before_any_nominees(authenticated_client, db_session):
    page = authenticated_client.get("/awards/the-game-awards-2026").text
    assert 'data-award-add="game/hades-ii-2025"' in page
    added = authenticated_client.post("/api/awards/the-game-awards-2026/add", json={"id": "tv/the-last-of-us-2023"})
    assert added.json()["state"] == "created"
    assert db_session.query(models.TVShow).filter_by(title="The Last of Us").count() == 1


# ---------------------------------------------------------------- dashboard card

def test_dashboard_card(authenticated_client, db_session, demo, monkeypatch):
    card = authenticated_client.get("/api/awards/card").json()
    assert card["show"] and card["state"] == "open" and card["slug"] == SHOW
    assert card["picked"] == 0 and card["total"] == 3 and card["days_left"] == 20 and card["page"] == f"/awards/{SHOW}"
    authenticated_client.put(f"/api/awards/{SHOW}/ballot", json={"picks": {"game-of-the-year": "hades-ii"}})
    assert authenticated_client.get("/api/awards/card").json()["picked"] == 1
    # After the lock the card waits for a winner, then shows the score for two weeks.
    _lock(monkeypatch)
    assert authenticated_client.get("/api/awards/card").json() == {"show": False}
    awards.set_result(db_session, SHOW, "game-of-the-year", "hades-ii")
    card = authenticated_client.get("/api/awards/card").json()
    assert card["state"] == "locked" and card["correct"] == 1 and card["judged"] == 1 and card["decided"] == 1
    monkeypatch.setattr(awards, "_now", lambda: datetime(2026, 12, 30))
    assert authenticated_client.get("/api/awards/card").json() == {"show": False}


def test_no_card_while_no_show_has_nominees(authenticated_client, monkeypatch):
    monkeypatch.setattr(awards, "_now", lambda: datetime(2026, 11, 12))
    for slug, show in awards.ordered():
        monkeypatch.setitem(awards_data.SHOWS, slug, dict(show, categories=[]))
    assert authenticated_client.get("/api/awards/card").json() == {"show": False}
    page = authenticated_client.get("/").text
    assert 'id="awardsBallot"' in page and "/static/awards.js?v=" in page
