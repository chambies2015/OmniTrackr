"""Fill in your year (Nov 26 2026): dating finishes the recap is missing, the emailed page and the December email."""
import asyncio
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

import pytest

from app import auth, challenges, models, year_fill, year_in_review
from app.site_traffic import RECORDER, clean_path

NOW = datetime(2026, 12, 3, 12, 0)


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    monkeypatch.setattr(year_fill, "_now", lambda: NOW)
    monkeypatch.setattr(RECORDER, "enabled", True)
    monkeypatch.setattr(RECORDER, "flush_due", lambda: False)
    RECORDER._pending.clear()
    yield
    RECORDER._pending.clear()


def counted(key):
    return sum(amount for (_, kind, name), amount in RECORDER._pending.items() if kind == "yearfill" and name == key)


def member(db, name="reader", *, created=datetime(2026, 3, 1), verified=True, seen_days=40):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_verified=verified,
                       is_active=True, created_at=created, last_login_at=NOW - timedelta(days=seen_days))
    db.add(user)
    db.flush()
    return user


def save(db, user, model=models.Movie, title="Dune", added=None, **fields):
    row = model(title=title, user_id=user.id, added_at=added, **fields)
    db.add(row)
    db.flush()
    return row


def headers_for(user):
    return {"Authorization": f"Bearer {auth.create_user_access_token(user)}"}


def finishes(db, user):
    return db.query(models.ActivityEntry).filter_by(user_id=user.id, action="completed").all()


class _KeepOpen:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self):
        pass


def run_send(db, sent, now=NOW):
    async def sender(to, subject, html, unsubscribe_url):
        sent.append((to, subject, html, unsubscribe_url))
    return asyncio.run(year_fill.send_due(lambda: _KeepOpen(db), now=now, sender=sender))


# ---------------------------------------------------------------- what to ask about

def test_years_and_months():
    assert year_fill.fill_years(date(2026, 12, 3)) == [2026]
    assert year_fill.fill_years(date(2027, 1, 20)) == [2027, 2026]   # last year's recap is still promoted
    assert year_fill.fill_years(date(2027, 2, 1)) == [2027]
    assert year_fill.fill_years(date(2025, 12, 3)) == []             # nothing was dated before 2026
    months = year_fill.months_for(2026, date(2026, 12, 3))
    assert [m["short"] for m in months][:3] == ["Jan", "Feb", "Mar"] and len(months) == 12
    assert months[-1]["current"] and not months[0]["current"]
    assert len(year_fill.months_for(2027, date(2027, 1, 20))) == 1
    assert len(year_fill.months_for(2026, date(2027, 1, 20))) == 12 and not any(
        m["current"] for m in year_fill.months_for(2026, date(2027, 1, 20)))
    assert year_fill.dated_from(2026) == "September" and year_fill.dated_from(2027) is None


def test_undated_titles_are_the_finished_ones_with_no_date(db_session):
    user = member(db_session)
    undated = save(db_session, user, title="Arrival", watched=True, year=2016)
    logged = save(db_session, user, title="Heat", watched=True)
    db_session.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=logged.id, title="Heat",
                                        action="completed", source="automatic", occurred_at=datetime(2026, 10, 2)))
    moment = save(db_session, user, model=models.Book, title="Piranesi", read=True)
    db_session.add(models.CompletionMoment(user_id=user.id, category="books", item_id=moment.id, title="Piranesi",
                                           completed_at=datetime(2026, 9, 20)))
    save(db_session, user, title="   ", watched=True)                     # a blank title is never asked about
    other = member(db_session, "other")
    save(db_session, other, title="Not mine", watched=True)
    db_session.commit()
    cards, total = year_fill.undated(db_session, user.id, 2026)
    assert total == 1 and [c["title"] for c in cards] == ["Arrival"]
    assert cards[0]["kind"] == "undated" and cards[0]["year"] == 2016 and cards[0]["label"] == "Movie"
    assert cards[0]["question"] == "When did you watch it?"
    assert cards[0]["id"] == undated.id


def test_still_on_your_list_skips_this_month_and_podcasts(db_session):
    user = member(db_session)
    save(db_session, user, title="Old save", added=datetime(2026, 5, 2))
    unknown = save(db_session, user, title="No add date")
    db_session.query(models.Movie).filter_by(id=unknown.id).update({"added_at": None})   # saved before add dates
    save(db_session, user, title="Saved this month", added=datetime(2026, 12, 2))
    save(db_session, user, model=models.Podcast, title="Serial", added=datetime(2026, 4, 1))
    save(db_session, user, title="Done already", watched=True, added=datetime(2026, 5, 1))
    db_session.commit()
    cards, total = year_fill.unfinished(db_session, user.id, 2026, today=NOW.date())
    assert total == 2
    assert [c["title"] for c in cards] == ["Old save", "No add date"]   # newest saves first, unknown last
    assert cards[0]["question"] == "Did you watch it in 2026?"


# ---------------------------------------------------------------- answering

def test_an_earlier_month_dates_the_finish_on_the_15th(db_session):
    user = member(db_session)
    movie = save(db_session, user, title="Arrival", watched=True, rating=9.0)
    db_session.commit()
    result = year_fill.answer(db_session, user, 2026, "movies", movie.id, "month", 6, now=NOW)
    assert result == {"state": "month", "kind": "undated", "month": 6, "title": "Arrival"}
    entry = finishes(db_session, user)[0]
    assert entry.source == year_fill.FILLED_SOURCE and entry.occurred_at == datetime(2026, 6, 15, 12, 0)
    assert entry.rating == 9.0 and entry.item_id == movie.id
    # The recap counts it and calls June the busiest month; it isn't an active day or a streak.
    assert year_in_review.finished_counts(db_session, user.id, 2026)["movies"] == 1
    recap = year_in_review.build(db_session, user, 2026)
    assert recap["busiest_month"]["month"] == "June" and recap["active_days"] == 0
    # June's challenge never sees it, and the title is no longer asked about.
    assert challenges._finishes(db_session, user.id, "2026-06") == []
    assert year_fill.undated(db_session, user.id, 2026)[1] == 0
    # A second tap (another tab) keeps the first answer.
    again = year_fill.answer(db_session, user, 2026, "movies", movie.id, "month", 3, now=NOW)
    assert again["state"] == "already" and len(finishes(db_session, user)) == 1


def test_this_month_is_a_normal_tick(db_session):
    user = member(db_session)
    movie = save(db_session, user, title="Arrival", added=datetime(2026, 4, 1))
    db_session.commit()
    result = year_fill.answer(db_session, user, 2026, "movies", movie.id, "month", 12, now=NOW)
    assert result["kind"] == "open"
    db_session.refresh(movie)
    assert movie.watched is True
    entry = finishes(db_session, user)[0]
    assert entry.source == "automatic"       # counts for December's challenge like any tick


def test_before_and_skip_change_nothing_in_the_library(db_session):
    user = member(db_session)
    old = save(db_session, user, title="Heat", watched=True)
    unsure = save(db_session, user, title="Alien", watched=True)
    db_session.commit()
    year_fill.answer(db_session, user, 2026, "movies", old.id, "before", now=NOW)
    year_fill.answer(db_session, user, 2026, "movies", unsure.id, "skip", now=NOW)
    assert finishes(db_session, user) == []
    assert year_fill.undated(db_session, user.id, 2026)[1] == 0
    # "Before 2026" holds for 2027 too; "not sure" is asked again next year.
    later = datetime(2027, 3, 1)
    assert [c["title"] for c in year_fill.undated(db_session, user.id, 2027)[0]] == ["Alien"]
    assert year_fill.is_fill_year(2027, later.date())


def test_a_month_ticks_off_a_title_still_on_the_list_and_undo_takes_it_back(db_session):
    user = member(db_session)
    book = save(db_session, user, model=models.Book, title="Piranesi", added=datetime(2026, 2, 1))
    db_session.commit()
    result = year_fill.answer(db_session, user, 2026, "books", book.id, "month", 3, now=NOW)
    assert result["kind"] == "open"
    db_session.refresh(book)
    assert book.read is True and len(finishes(db_session, user)) == 1
    record = db_session.query(models.YearFillAnswer).one()
    assert record.ticked and record.entry_id == finishes(db_session, user)[0].id
    assert year_fill.undo(db_session, user, 2026, "books", book.id) is True
    db_session.refresh(book)
    assert book.read is False and finishes(db_session, user) == []
    assert db_session.query(models.YearFillAnswer).count() == 0
    assert year_fill.undo(db_session, user, 2026, "books", book.id) is False
    # Finished long ago: ticked off, with no 2026 date.
    year_fill.answer(db_session, user, 2026, "books", book.id, "before", now=NOW)
    db_session.refresh(book)
    assert book.read is True and finishes(db_session, user) == []
    assert year_fill.undated(db_session, user.id, 2026)[1] == 0   # and not asked again as "no date"


def test_answers_check_their_input(db_session):
    user = member(db_session)
    movie = save(db_session, user, title="Arrival", watched=True)
    podcast = save(db_session, user, model=models.Podcast, title="Serial")
    db_session.commit()
    for bad in [("month", None), ("month", 0), ("month", 13), ("month", True), ("maybe", None)]:
        with pytest.raises(ValueError):
            year_fill.answer(db_session, user, 2026, "movies", movie.id, bad[0], bad[1], now=NOW)
    with pytest.raises(ValueError):
        year_fill.answer(db_session, user, 2025, "movies", movie.id, "month", 3, now=NOW)
    with pytest.raises(ValueError):
        year_fill.answer(db_session, user, 2026, "podcasts", podcast.id, "month", 3, now=NOW)
    # In January, last year's months all count as earlier months, and this year only has January.
    january = datetime(2027, 1, 10, 9, 0)
    with pytest.raises(ValueError):
        year_fill.answer(db_session, user, 2027, "movies", movie.id, "month", 2, now=january)
    assert year_fill.answer(db_session, user, 2026, "movies", movie.id, "month", 12, now=january)["state"] == "month"
    assert finishes(db_session, user)[0].source == year_fill.FILLED_SOURCE
    other = member(db_session, "other")
    assert year_fill.answer(db_session, other, 2026, "movies", movie.id, "month", 3, now=NOW) is None


def test_the_rest_and_bringing_them_back(db_session):
    user = member(db_session)
    for n in range(5):
        save(db_session, user, title=f"Film {n}", watched=True)
    first = save(db_session, user, title="Dated", watched=True)
    db_session.commit()
    year_fill.answer(db_session, user, 2026, "movies", first.id, "month", 4, now=NOW)
    assert year_fill.answer_rest(db_session, user, 2026, "undated", now=NOW) == 5
    assert year_fill.undated(db_session, user.id, 2026)[1] == 0
    assert year_fill.bring_back(db_session, user, 2026) == 5
    assert year_fill.undated(db_session, user.id, 2026)[1] == 5
    assert len(finishes(db_session, user)) == 1                   # the dated one stays dated


def test_deck_counts_and_state(db_session):
    user = member(db_session)
    for n in range(year_fill.DECK_LIMIT + 3):
        save(db_session, user, title=f"Film {n}", watched=True)
    db_session.commit()
    data = year_fill.state(db_session, user.id, 2026, NOW.date())
    assert data["undated_total"] == year_fill.DECK_LIMIT + 3 and len(data["undated"]) == year_fill.DECK_LIMIT
    assert data["undated"][0]["title"] == f"Film {year_fill.DECK_LIMIT + 2}"    # newest rows first
    assert data["finished_total"] == 0 and data["filled"] == 0 and len(data["months"]) == 12


# ---------------------------------------------------------------- the member page

def test_member_page_and_api(client, db_session):
    user = member(db_session)
    movie = save(db_session, user, title="Arrival", watched=True, year=2016)
    book = save(db_session, user, model=models.Book, title="Piranesi", added=datetime(2026, 2, 1))
    db_session.commit()
    headers = headers_for(user)
    page = client.get("/year-in-review/2026/fill", headers=headers)
    assert page.status_code == 200
    assert page.headers["cache-control"] == "private, no-store" and "noindex" in page.headers["x-robots-tag"]
    html = page.text
    assert "Fill in your 2026" in html and "started dating what you finish in September 2026" in html
    assert 'data-category="movies"' in html and "Arrival" in html and "Piranesi" in html
    assert 'data-answer="month" data-month="6"' in html and 'aria-label="December 2026 (this month)"' in html
    assert "Before 2026" in html and "Not yet" in html
    assert "/static/year-fill.js?v=" in html and "/static/year-fill.css?v=" in html

    answered = client.post("/api/year-in-review/2026/fill", headers=headers,
                           json={"category": "movies", "id": movie.id, "answer": "month", "month": 5})
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["state"] == "month" and body["finished_total"] == 1 and body["filled"] == 1
    assert body["undated_left"] == 0 and body["open_left"] == 1
    assert counted("dated_page") == 1
    done = client.post("/api/year-in-review/2026/fill", headers=headers,
                       json={"category": "books", "id": book.id, "answer": "skip"}).json()
    assert done["open_left"] == 0 and counted("skipped_page") == 1 and counted("all_done_page") == 1
    undone = client.post("/api/year-in-review/2026/fill/undo", headers=headers,
                         json={"category": "movies", "id": movie.id}).json()
    assert undone["undone"] is True and undone["finished_total"] == 0 and undone["undated_left"] == 1
    assert client.get("/api/year-in-review/2026/fill", headers=headers).json()["undated_total"] == 1
    rest = client.post("/api/year-in-review/2026/fill/rest", headers=headers, json={"kind": "undated"}).json()
    assert rest["answered"] == 1 and rest["undated_left"] == 0
    back = client.post("/api/year-in-review/2026/fill/bring-back", headers=headers).json()
    assert back["brought_back"] == 2 and back["undated_left"] == 1 and back["open_left"] == 1

    bad = client.post("/api/year-in-review/2026/fill", headers=headers,
                      json={"category": "movies", "id": movie.id, "answer": "month", "month": 13})
    assert bad.status_code == 422
    other_shelf = client.post("/api/year-in-review/2026/fill", headers=headers,
                              json={"category": "users", "id": movie.id, "answer": "skip"})
    assert other_shelf.status_code == 422
    gone = client.post("/api/year-in-review/2026/fill", headers=headers,
                       json={"category": "movies", "id": 999999, "answer": "skip"})
    assert gone.status_code == 404
    assert client.get("/api/year-in-review/2025/fill", headers=headers).status_code == 404
    assert client.post("/api/year-in-review/2026/fill",
                       json={"category": "movies", "id": movie.id, "answer": "skip"}).status_code == 401


def test_member_page_redirects(client, db_session):
    user = member(db_session)
    db_session.commit()
    signed_out = client.get("/year-in-review/2026/fill", follow_redirects=False)
    assert signed_out.status_code == 302 and signed_out.headers["location"] == "/#login"
    old = client.get("/year-in-review/2025/fill", headers=headers_for(user), follow_redirects=False)
    assert old.status_code == 302 and old.headers["location"] == "/year-in-review"


def test_empty_page_leads_with_the_big_ones(client, db_session):
    user = member(db_session)
    db_session.commit()
    html = client.get("/year-in-review/2026/fill", headers=headers_for(user)).text
    done = re.search(r'<section class="yf-done"[^>]*>', html).group(0)
    # Nothing to date and nothing finished: the year's big releases are the page (app/year_catchup.py).
    assert "hidden" in done and "yours is empty so far" in html and "2026’s big ones" in html
    assert re.search(r'<section class="yf-section yf-section--deck"[^>]*hidden', html)


def test_filled_in_page_still_says_so(client, db_session, monkeypatch):
    from app import year_catchup
    monkeypatch.setattr(year_catchup, "available", lambda year, today=None: False)
    user = member(db_session)
    db_session.commit()
    html = client.get("/year-in-review/2026/fill", headers=headers_for(user)).text
    done = re.search(r'<section class="yf-done"[^>]*>', html).group(0)
    assert "hidden" not in done and "Your 2026 is filled in" in html and "big ones" not in html


def test_season_banner_and_recap_box(client, db_session, monkeypatch):
    monkeypatch.setattr(year_in_review, "season_year", lambda today=None: 2026)
    user = member(db_session)
    save(db_session, user, title="Arrival", watched=True)
    db_session.commit()
    headers = headers_for(user)
    season = client.get("/api/year-in-review-season", headers=headers).json()
    assert season["fill"] == {"year": 2026, "undated": 1, "open": 0, "filled": 0,
                              "url": "/year-in-review/2026/fill", "dated_from": "September"}
    client.cookies.set(auth.AUTH_COOKIE_NAME, auth.create_user_access_token(user))   # the recap page reads the cookie
    recap = client.get("/year-in-review/2026").text
    assert "Your recap starts in September" in recap and 'href="/year-in-review/2026/fill"' in recap
    assert "1 title in your library is ticked off with no date" in recap


# ---------------------------------------------------------------- the emailed page

def _token_for(db, user, refs):
    return year_fill.make_token(user.id, 2026, [{"category": c, "id": i} for c, i in refs])


def test_token_round_trip_and_tampering(db_session):
    user = member(db_session)
    movie = save(db_session, user, watched=True)
    token = _token_for(db_session, user, [("movies", movie.id)])
    assert year_fill.read_token(token) == {"user_id": user.id, "year": 2026, "items": [("movies", movie.id)],
                                           "catchup": False}
    assert year_fill.read_token(token[:-2] + ("aa" if not token.endswith("aa") else "bb")) is None
    assert year_fill.read_token("") is None and year_fill.read_token("x" * 600) is None
    from app import check_in
    # A check-in link is signed with another salt and never opens this page.
    assert year_fill.read_token(check_in.make_token(user.id, [{"category": "movies", "id": movie.id}], "checkin")) is None


def test_emailed_page_answers_without_signing_in(client, db_session):
    user = member(db_session)
    movie = save(db_session, user, title="Arrival", watched=True)
    book = save(db_session, user, model=models.Book, title="Piranesi", added=datetime(2026, 2, 1))
    other = save(db_session, user, title="Not in the email", watched=True)
    db_session.commit()
    token = _token_for(db_session, user, [("movies", movie.id), ("books", book.id)])
    path = f"/fill-in/{token}"
    chrome = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/130.0 Safari/537.36"}
    page = client.get(path, headers=chrome)
    assert page.status_code == 200 and "Arrival" in page.text and "Piranesi" in page.text
    assert "Not in the email" not in page.text
    assert '<meta name="referrer" content="same-origin">' in page.text and "noindex" in page.headers["x-robots-tag"]
    assert 'name="choice" value="month-6"' in page.text
    assert counted("opened_email") == 1

    saved = client.post(path, data={"item": "0", "choice": "month-6"}, follow_redirects=False)
    assert saved.status_code == 303 and saved.headers["location"] == "?r=1#yf-0"
    assert finishes(db_session, user)[0].occurred_at == datetime(2026, 6, 15, 12, 0)
    assert counted("dated_email") == 1
    after = client.get(path + "?r=1", headers=chrome).text
    assert "Finished in June" in after and counted("opened_email") == 1   # our own redirect isn't an open
    client.post(path, data={"item": "1", "choice": "skip"})
    assert counted("all_done_email") == 1
    assert "All filled in" in client.get(path).text
    # "Change" takes an answer back.
    client.post(path, data={"item": "0", "choice": "undo"})
    assert finishes(db_session, user) == [] and counted("undone_email") == 1
    # Indexes outside the link and odd choices change nothing.
    for data in ({"item": "2", "choice": "month-3"}, {"item": "x", "choice": "skip"}, {"item": "0", "choice": "month-x"},
                 {"item": "0", "choice": "month-13"}, {"item": "0", "choice": "drop"}):
        assert client.post(path, data=data, follow_redirects=False).status_code == 303
    assert finishes(db_session, user) == []
    db_session.refresh(other)
    assert db_session.query(models.YearFillAnswer).filter_by(item_id=other.id).count() == 0
    assert visits_recorded(db_session, user)


def visits_recorded(db, user):
    db.refresh(user)
    return user.last_seen_on is not None


def test_emailed_page_expired_or_tampered(client, db_session):
    user = member(db_session)
    movie = save(db_session, user, watched=True)
    db_session.commit()
    assert client.get("/fill-in/not-a-token").status_code == 404
    token = _token_for(db_session, user, [("movies", movie.id)])
    db_session.delete(movie)
    db_session.commit()
    assert client.get(f"/fill-in/{token}").status_code == 404           # every title is gone
    assert client.post("/fill-in/not-a-token", data={"item": "0", "choice": "skip"}).status_code == 404
    assert clean_path(f"/fill-in/{token}") == "/fill-in/(private link)"


# ---------------------------------------------------------------- the December email

def test_who_gets_the_email(db_session):
    due = member(db_session, "due")
    save(db_session, due, watched=True)
    empty = member(db_session, "empty")                                     # no library at all
    opted = member(db_session, "opted")
    save(db_session, opted, watched=True)
    db_session.add(models.EmailOptOut(user_id=opted.id))
    weekly = member(db_session, "weekly")
    save(db_session, weekly, watched=True)
    db_session.add(models.EmailDigestSubscription(user_id=weekly.id, token="weekly-token"))
    december = member(db_session, "december", created=datetime(2026, 12, 2))
    save(db_session, december, watched=True)
    unverified = member(db_session, "unverified", verified=False)
    save(db_session, unverified, watched=True)
    recent = member(db_session, "recent")
    save(db_session, recent, watched=True)
    db_session.add(models.EmailCampaignSend(campaign_key="yearbook-1-notes-1", user_id=recent.id, status="sent",
                                            sent_at=NOW - timedelta(hours=20)))
    db_session.commit()
    # An empty library gets the year's big ones (app/year_catchup.py), so it is due too.
    assert [user.username for user in year_fill.due_members(db_session, NOW)] == ["due", "empty"]
    assert year_fill.due_members(db_session, datetime(2026, 12, 15, 0, 1)) == []
    assert year_fill.due_members(db_session, datetime(2026, 11, 30, 23, 0)) == []
    assert december and unverified


def test_email_wording(db_session):
    user = member(db_session)
    save(db_session, user, title="Arrival", watched=True)
    save(db_session, user, title="Heat", watched=True)
    db_session.commit()
    subject, html, text, _ = year_fill.email_for(db_session, user, NOW)
    assert subject == "Your 2026 recap is missing 2 titles"
    assert "Right now your recap is empty, because OmniTrackr only started dating what you finish in September." in text
    assert "2 titles in your library are ticked off with no date" in text
    assert "/fill-in/" in html and "Pick the month" in html and "Unsubscribe from product updates" in html
    assert "Arrival" in html and "Heat" in html
    # Only "still on your list" titles.
    other = member(db_session, "lister")
    save(db_session, other, title="Piranesi", model=models.Book, added=datetime(2026, 5, 1))
    db_session.commit()
    assert year_fill.email_for(db_session, other, NOW)[0] == "Did you get to these in 2026?"
    assert "Got to any of 2026's big releases" in text
    # Nothing to fill in, and five finishes or more: the recap itself, with the big ones linked at the bottom.
    done = member(db_session, "done")
    for n, title in enumerate(("Alien", "Aliens", "Heat", "Ronin", "Thief")):
        movie = save(db_session, done, title=title, watched=True)
        db_session.add(models.ActivityEntry(user_id=done.id, category="movies", item_id=movie.id, title=title,
                                            action="completed", source="automatic",
                                            occurred_at=datetime(2026, 10, 1 + n)))
    db_session.commit()
    subject, html, text, _ = year_fill.email_for(db_session, done, NOW)
    assert subject == "Your 2026 in review is ready" and "Play your year" in html
    assert "So far your recap has 5 finishes, all from September on" in text
    assert "#big-ones" in html and "Fill in your 2026" not in html
    # Nothing at all: the big ones email (tests/test_year_catchup.py has the rest).
    nobody = member(db_session, "nobody")
    db_session.commit()
    assert "which did you get to in 2026?" in year_fill.email_for(db_session, nobody, NOW)[0]


def test_send_due_respects_the_switch_and_sends_once(db_session):
    user = member(db_session)
    save(db_session, user, title="Arrival", watched=True)
    db_session.commit()
    sent = []
    assert run_send(db_session, sent)["sent"] == 0                         # draft: nothing goes
    year_fill.set_status(db_session, "sending")
    assert run_send(db_session, sent, now=datetime(2026, 11, 30, 12, 0))["sent"] == 0   # before December 1
    assert run_send(db_session, sent)["sent"] == 1
    assert sent[0][0] == "reader@example.com" and "missing 1 title" in sent[0][1]
    assert counted("sent") == 1
    assert run_send(db_session, sent, now=NOW + timedelta(days=4))["sent"] == 0   # once a year
    claim = db_session.query(models.EmailCampaignSend).filter_by(user_id=user.id).one()
    assert claim.campaign_key == "yearfill-2026" and claim.status == "sent"
    info = year_fill.status(db_session, NOW)
    assert info["status"] == "sending" and info["sent_all_time"] == 1 and info["window_open"]
    assert info["window"] == "December 1 to 14, 2026"


def test_members_with_nothing_to_say_do_not_hold_up_the_rest(db_session, monkeypatch):
    from app import year_catchup
    monkeypatch.setattr(year_catchup, "available", lambda year, today=None: False)   # no big ones to offer
    for n in range(12):
        quiet = member(db_session, f"quiet{n}")
        movie = save(db_session, quiet, title=f"Old film {n}", watched=True)
        # Imported with a 2024 diary date: no fill-in question and nothing finished in 2026.
        db_session.add(models.ActivityEntry(user_id=quiet.id, category="movies", item_id=movie.id, title=movie.title,
                                            action="completed", source="import", occurred_at=datetime(2024, 5, 1)))
    late = member(db_session, "late")
    save(db_session, late, title="Arrival", watched=True)
    year_fill.set_status(db_session, "sending")
    db_session.commit()
    sent = []
    assert run_send(db_session, sent)["sent"] == 1 and sent[0][0] == "late@example.com"


def test_send_due_stops_at_the_daily_limit(db_session, monkeypatch):
    monkeypatch.setenv("YEAR_FILL_DAILY_LIMIT", "2")
    for n in range(4):
        user = member(db_session, f"m{n}")
        save(db_session, user, watched=True)
    year_fill.set_status(db_session, "sending")
    db_session.commit()
    sent = []
    assert run_send(db_session, sent)["sent"] == 2
    assert run_send(db_session, sent)["sent"] == 0


def test_site_stats_card(client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAMES", "boss")
    owner = member(db_session, "boss")
    save(db_session, owner, title="Arrival", watched=True)
    db_session.commit()
    headers = headers_for(owner)
    stats = client.get("/api/site-stats/overview", headers=headers)
    assert stats.status_code == 200
    card = stats.json()["year_fill"]
    assert card["status"] == "draft" and card["daily_limit"] == 30
    preview = client.get("/site-stats/year-fill-preview", headers=headers)
    assert preview.status_code == 200 and "Preview only" in preview.text and "missing 1 title" in preview.text
    started = client.post("/api/site-stats/year-fill", headers=headers, json={"action": "start"})
    assert started.status_code == 200 and started.json()["status"] == "sending"
    paused = client.post("/api/site-stats/year-fill", headers=headers, json={"action": "pause"})
    assert paused.json()["status"] == "paused"
    stranger = member(db_session, "stranger")
    db_session.commit()
    assert client.post("/api/site-stats/year-fill", headers=headers_for(stranger),
                       json={"action": "start"}).status_code == 403


def test_trending_and_memories_skip_filled_in_finishes(db_session):
    from app import memories, trending
    import inspect
    assert '"filled-in"' in inspect.getsource(trending)
    assert '"filled-in"' in inspect.getsource(memories.collect)
    assert urlsplit(year_fill.link_for("abc", 2)).fragment == "yf-2"
