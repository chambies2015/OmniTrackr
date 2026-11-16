"""Nov 16 2026: email sign-up form steps in Site stats, and why title pages showed errors.

Site stats counted episode guide and release calendar lookups as title page details, a
Wikidata rate limit threw away the Wikipedia overview too, and anime films never matched.
"""
import asyncio
import json
from pathlib import Path

import pytest

from app import funnel, models, title_metadata
from app.site_traffic import RECORDER
from tests.test_title_pages import FakeClient, FakeResponse

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


class Response429(FakeResponse):
    def __init__(self, retry_after="8"):
        super().__init__({}, 429)
        self.headers = {"retry-after": retry_after}


def summary_route(pages):
    def match(url, params):
        return url.startswith("https://en.wikipedia.org/api/rest_v1/page/summary/") and url.rsplit("/", 1)[1] in pages
    return match


class WikidataLimited(FakeClient):
    """Wikidata answers 429; Wikipedia's summaries still work."""

    def __init__(self, pages, routes=()):
        super().__init__(list(routes))
        self.pages = pages

    async def get(self, url, params=None, headers=None, timeout=None, follow_redirects=None):
        if url.startswith("https://www.wikidata.org/"):
            self.calls.append((url, params or {}))
            return Response429()
        if summary_route(self.pages)(url, params):
            self.calls.append((url, {}))
            return FakeResponse(self.pages[url.rsplit("/", 1)[1]])
        return await super().get(url, params, headers, timeout, follow_redirects)


INCEPTION = {"type": "standard", "title": "Inception", "description": "2010 film by Christopher Nolan",
             "extract": "Inception is a 2010 science fiction action film.", "wikibase_item": "Q25188",
             "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Inception"}}}


# ---------------------------------------------------------------- anime films

@pytest.mark.parametrize("description,expected", [
    ("2016 Japanese animated film directed by Makoto Shinkai", True),
    ("2001 Japanese anime film by Hayao Miyazaki", True),
    ("Japanese anime television series", True),
    ("1995 American animated film", False),
    ("2017 American live-action film based on the anime", False),
    ("Japanese animated film series", False),
    ("2016 film", False),
])
def test_anime_films_count_as_anime(description, expected):
    assert title_metadata._describes("anime", description, 2016 if "2016" in description else None) is expected


def test_your_name_matches_its_wikidata_entry():
    client = FakeClient([(lambda url, params: params.get("action") == "wbsearchentities", {"search": [
        {"id": "Q22678", "label": "Your Name", "description": "2016 Japanese animated film directed by Makoto Shinkai"},
    ]})])
    assert asyncio.run(title_metadata._wikidata_find(client, "anime", "Your Name.", 2016)) == "Q22678"


# ---------------------------------------------------------------- Wikidata rate limits

def test_a_rate_limited_wikidata_still_gives_the_wikipedia_overview():
    client = WikidataLimited({"Inception": INCEPTION})
    data = asyncio.run(title_metadata.fetch(client, "movie", "Inception", 2010))
    assert data["description"].startswith("Inception is a 2010")
    assert data["description_source"]["name"] == "Wikipedia"
    assert data["partial"] is True  # looked at again in a day, when Wikidata may answer


def test_the_wikipedia_overview_must_fit_the_kind_and_year():
    wrong = dict(INCEPTION, description="1978 film by someone else")
    client = WikidataLimited({"Inception": wrong})
    with pytest.raises(title_metadata.SourceUnavailable):
        asyncio.run(title_metadata.fetch(client, "movie", "Inception", 2010))
    # A disambiguated article is tried after the plain one.
    pages = {"Dune": {"type": "standard", "title": "Dune", "description": "1965 novel by Frank Herbert", "extract": "Novel."},
             "Dune_%282021_film%29": dict(INCEPTION, title="Dune (2021 film)", description="2021 film by Denis Villeneuve",
                                          extract="Dune is a 2021 film.")}
    data = asyncio.run(title_metadata.fetch(WikidataLimited(pages), "movie", "Dune", 2021))
    assert data["description"] == "Dune is a 2021 film."


def test_a_429_pauses_that_source_for_its_retry_after():
    client = WikidataLimited({"Inception": INCEPTION})
    asyncio.run(title_metadata.fetch(client, "movie", "Inception", 2010))
    asked = len([call for call in client.calls if "wikidata" in call[0]])
    assert asked == 1  # the first 429 stops the rest of the Wikidata calls for this page
    asyncio.run(title_metadata.fetch(client, "movie", "Inception", 2010))
    assert len([call for call in client.calls if "wikidata" in call[0]]) == asked
    # Wikipedia is a different host and is still asked.
    assert any("wikipedia" in call[0] for call in client.calls)
    title_metadata.clear_cooldowns()
    asyncio.run(title_metadata.fetch(client, "movie", "Inception", 2010))
    assert len([call for call in client.calls if "wikidata" in call[0]]) == asked + 1


@pytest.mark.parametrize("header,expected", [("8", 8.0), ("0", 1.0), ("100000", title_metadata.COOLDOWN_MAX),
                                             ("Wed, 21 Oct 2026 07:28:00 GMT", title_metadata.COOLDOWN_DEFAULT)])
def test_retry_after_is_read_and_bounded(header, expected):
    assert title_metadata._retry_after(Response429(header)) == expected
    assert title_metadata._retry_after(FakeResponse({}, 429)) == title_metadata.COOLDOWN_DEFAULT


# ---------------------------------------------------------------- reasons and Site stats

def test_failed_lookups_keep_their_reason_but_never_read_as_facts(db_session):
    class Broken:
        async def get(self, *args, **kwargs):
            raise RuntimeError("down")

    assert asyncio.run(title_metadata.get_or_fetch(db_session, Broken(), "movie", "interstellar", "Interstellar", 2014)) is None
    row = db_session.query(models.TitleMetadata).filter_by(key="movie:interstellar:2014").one()
    assert row.status == "error" and json.loads(row.data) == {"reason": "down"}
    assert title_metadata.cached(db_session, "movie:interstellar:2014")[0] is None

    class Empty:
        async def get(self, *args, **kwargs):
            return FakeResponse({}, 404)

    asyncio.run(title_metadata.get_or_fetch(db_session, Empty(), "movie", "nobody", "Nobody Knows This", 1999))
    row = db_session.query(models.TitleMetadata).filter_by(key="movie:nobody:1999").one()
    assert row.status == "miss" and json.loads(row.data) == {"reason": "No source had this title"}


def test_a_failed_refresh_keeps_good_facts_and_their_status(db_session):
    title_metadata.store(db_session, "movie:a:2000", {"description": "good"}, "ok")
    title_metadata.store(db_session, "movie:a:2000", title_metadata.problem(RuntimeError("down")), "error")
    row = db_session.query(models.TitleMetadata).filter_by(key="movie:a:2000").one()
    assert row.status == "ok" and json.loads(row.data) == {"description": "good"}


def test_timeouts_say_how_long_was_waited():
    assert title_metadata.problem(asyncio.TimeoutError(), 8.0) == {"reason": "Sources took longer than 8 s"}


def test_site_stats_counts_episode_guides_and_calendars_apart(authenticated_client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser")
    title_metadata.store(db_session, "movie:a:2000", {"description": "x"}, "ok")
    title_metadata.store(db_session, "anime:your name.:2016", {"reason": "www.wikidata.org answered 429 (rate limited)"}, "error")
    title_metadata.store(db_session, "episodes:tv:lost:2004", None, "error")
    title_metadata.store(db_session, "airing:anime:frieren:2023", None, "error")
    title_metadata.store(db_session, "airing:tv:lost:2004", {"ended": True}, "ended")
    title_metadata.store(db_session, "airing:tv:the office:2005", None, "miss")
    details = authenticated_client.get("/api/site-stats/overview").json()["system"]["title_details"]
    assert (details["found"], details["not_found"], details["errors"]) == (1, 0, 1)
    assert details["episode_guides"] == {"found": 0, "not_found": 0, "errors": 1}
    assert details["release_schedules"] == {"found": 1, "not_found": 1, "errors": 1}
    assert details["problems"] == [{"kind": "anime", "title": "your name.", "year": "2016", "status": "error",
                                    "reason": "www.wikidata.org answered 429 (rate limited)",
                                    "checked": details["problems"][0]["checked"]}]


def test_errors_saved_before_reasons_were_kept_say_so(authenticated_client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "testuser")
    title_metadata.store(db_session, "book:dune:", None, "error")
    problem = authenticated_client.get("/api/site-stats/overview").json()["system"]["title_details"]["problems"][0]
    assert problem["year"] is None and problem["reason"] == "Saved before reasons were kept"


def test_site_stats_page_shows_the_new_lines():
    script = (STATIC / "site-stats.js").read_text(encoding="utf-8")
    assert "Release calendar schedules" in script and "Latest title page problems" in script
    assert "Email sign-up form: " in script and "fillList('emailSignupForm'" in script


# ---------------------------------------------------------------- email form steps

@pytest.fixture
def recorder(monkeypatch):
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield RECORDER
    RECORDER._pending.clear()


def test_email_form_steps_are_accepted_from_the_browser(client, recorder):
    for event, _ in funnel.EMAIL_FORM:
        assert client.post("/api/funnel", json={"event": event}, headers={"user-agent": "Mozilla/5.0 Chrome/131"}).status_code == 204
    counted = {key for (day, kind, key) in recorder._pending if kind == "funnel"}
    assert counted == {event for event, _ in funnel.EMAIL_FORM}


def test_email_form_summary_ends_at_the_server():
    counts = {"signup_email_opened": 5, "signup_email_typed": 3, "signup_email_password": 2,
              "signup_email_pressed": 1, "signup_submitted": 1, "google_account_created": 7}
    steps = funnel.summary(counts)["email_form"]
    assert [step["count"] for step in steps] == [5, 3, 2, 1, 1]
    assert steps[-1]["label"] == "Reached our server"


def test_auth_script_reports_each_email_step_once_per_visit():
    script = (STATIC / "auth.js").read_text(encoding="utf-8")
    for event, _ in funnel.EMAIL_FORM:
        assert f"reportFunnelEvent('{event}')" in script
        assert f"'{event}'" in script.split("const FUNNEL_ONCE_PER_VISIT")[1].split(";")[0]
    # Google buttons still count as starting to sign up, but not as opening the email form.
    assert "if (link.hasAttribute('data-google-signup')) reportSignupStart();" in script
