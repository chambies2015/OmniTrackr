"""Year in Review closing note (Ko-fi thank-you or ask) and the monthly challenge in the weekly email."""
from datetime import date, datetime, timedelta

import pytest

from app import challenges, digest, funnel, models, supporters


def _user(db_session):
    return db_session.query(models.User).filter(models.User.username == "testuser").one()


def _finish(client, path, payload, done_field):
    item = client.post(path, json=dict(payload, **{done_field: True})).json()
    response = client.post("/completion-moments/", json={"category": path.strip("/"), "item_id": item["id"]})
    assert response.status_code == 200, response.text
    return item


def _recap(client):
    _finish(client, "/movies/", {"title": "Arrival", "director": "D. Villeneuve", "year": 2016, "rating": 9}, "watched")
    return client.get(f"/year-in-review/{datetime.utcnow().year}").text


# ---------------------------------------------------------------- Year in Review support note

def test_recap_asks_members_who_have_not_supported(authenticated_client, db_session):
    page = _recap(authenticated_client)
    year = datetime.utcnow().year
    assert f"Help keep OmniTrackr free in {year + 1}" in page
    assert 'href="https://ko-fi.com/omnitrackr"' in page and "data-recap-kofi" in page
    assert supporters.supporter_code(_user(db_session).id) in page
    assert "Every tracking feature stays free" in page


def test_recap_thanks_current_supporters_instead_of_asking(authenticated_client, db_session):
    now = datetime.utcnow()
    db_session.add(models.Supporter(user_id=_user(db_session).id, since=datetime(2026, 9, 3),
                                    active_until=now + timedelta(days=10)))
    db_session.commit()
    page = _recap(authenticated_client)
    assert "Thank you for supporting OmniTrackr" in page and "since September 2026" in page
    assert "data-recap-kofi" not in page and "Help keep OmniTrackr free" not in page


def test_recap_thanks_lapsed_supporters_and_offers_a_renewal(authenticated_client, db_session):
    now = datetime.utcnow()
    db_session.add(models.Supporter(user_id=_user(db_session).id, since=now - timedelta(days=90),
                                    active_until=now - timedelta(days=5)))
    db_session.commit()
    page = _recap(authenticated_client)
    assert f"Thanks for supporting OmniTrackr in {now.year}" in page and "data-recap-kofi" in page


def test_empty_recap_has_no_ask(authenticated_client):
    page = authenticated_client.get(f"/year-in-review/{datetime.utcnow().year}").text
    assert "Nothing was logged this year yet" in page and "recap-support" not in page


def test_shared_recap_never_shows_the_owner_note(authenticated_client, client, db_session):
    _recap(authenticated_client)
    url = authenticated_client.put(f"/api/year-in-review/{datetime.utcnow().year}/share").json()["url"]
    path = url.split("://", 1)[1].split("/", 1)[1]
    page = client.get("/" + path).text
    assert "recap-support" not in page and supporters.supporter_code(_user(db_session).id) not in page


def test_recap_kofi_click_is_a_counted_browser_event():
    assert "recap_kofi_clicked" in funnel.CLIENT_EVENTS
    assert "recap_kofi_clicked" in {item["event"] for item in funnel.summary({})["guest"]}


# ---------------------------------------------------------------- weekly email challenge line

CHALLENGE = {
    "name": "Test the strange", "tagline": "A test challenge.", "published": "2026-10-10", "intro": ["x"],
    "steps": [
        {"kind": "total", "count": 2, "label": "Finish two titles", "detail": "d"},
        {"kind": "reflect", "count": 1, "label": "Rate one", "detail": "d"},
    ],
    "reflection": "",
}
REPORT = {"matches": [{"url": "/release-radar", "title": "Dune: Part Three", "label": "Movie",
                       "date": "2026-12-18", "reason": "You track Dune"}], "popular": []}


@pytest.fixture
def october(monkeypatch):
    monkeypatch.setitem(challenges.CHALLENGES, "2026-10", CHALLENGE)
    return date(2026, 10, 12)


def test_challenge_invitation_for_members_who_have_not_joined(authenticated_client, db_session, october):
    user = _user(db_session)
    line = digest.challenge_line(db_session, user.id, october)
    assert line["joined"] is False and line["days_left"] == 20
    subject, html, text = digest.build_digest("sam", REPORT, "https://x/unsub", challenge=line)
    assert "This month's challenge" in html and "Take the October challenge" in html
    assert "Two small steps, 20 days left" in html and "/#challenge" in text
    # Too late in the month to start, and months without a curated challenge, say nothing.
    assert digest.challenge_line(db_session, user.id, date(2026, 10, 27)) is None
    assert digest.challenge_line(db_session, user.id, date(2031, 3, 2)) is None


def test_challenge_progress_for_members_who_joined(authenticated_client, db_session, october):
    user = _user(db_session)
    challenges.join(db_session, user.id, "2026-10")
    db_session.add(models.CompletionMoment(user_id=user.id, category="movies", item_id=1, title="Arrival",
                                           rating=9, completed_at=datetime(2026, 10, 5)))
    db_session.commit()
    line = digest.challenge_line(db_session, user.id, october)
    assert line == {"joined": True, "name": "Test the strange", "days_left": 20, "done_steps": 1,
                    "total_steps": 2, "next": "Finish two titles", "next_count": 1, "next_target": 2}
    _subject, html, text = digest.build_digest("sam", REPORT, "https://x/unsub", challenge=line)
    assert "1 of 2 steps done, 20 days left." in html and "Next up: Finish two titles (1 of 2)." in html
    assert "See your challenge" in html and "Next up: Finish two titles (1 of 2)" in text


def test_finished_challenge_drops_out_of_the_email(authenticated_client, db_session, october):
    user = _user(db_session)
    challenges.join(db_session, user.id, "2026-10")
    for item_id, title in ((1, "Arrival"), (2, "Piranesi")):
        db_session.add(models.CompletionMoment(user_id=user.id, category="movies", item_id=item_id, title=title,
                                               rating=8, completed_at=datetime(2026, 10, 5)))
    db_session.commit()
    assert digest.challenge_line(db_session, user.id, october) is None


def test_challenge_never_forces_a_send(authenticated_client, db_session, october):
    line = digest.challenge_line(db_session, _user(db_session).id, october)
    assert digest.build_digest("sam", {"matches": [], "popular": []}, "https://x/unsub", challenge=line) is None
    assert "challenge" not in digest.build_digest("sam", REPORT, "https://x/unsub")[1]
