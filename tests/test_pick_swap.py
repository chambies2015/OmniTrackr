"""Pick swap: making one, joining by link, the draw, wrapping picks in secret, unwrap day and the emails."""
import asyncio
import html
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app import auth, models, pick_swap

ROOT = Path(__file__).resolve().parents[1]


def make_user(db, name, **extra):
    user = models.User(username=name, email=f"{name}@example.test", hashed_password="unused", is_active=True,
                       is_verified=True, **extra)
    db.add(user)
    db.commit()
    return user


def sign_in(client, user):
    client.headers["Authorization"] = "Bearer " + auth.create_access_token({"sub": user.username, "uid": user.id})


def sign_out(client):
    client.headers.pop("Authorization", None)
    client.cookies.clear()


def start(client, user, **extra):
    sign_in(client, user)
    body = {"name": "Office swap", "reveal_on": (date.today() + timedelta(days=10)).isoformat(),
            "wish": "Something funny", "kinds": [], **extra}
    response = client.post("/api/swaps", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def join(client, db, swap_id, user, wish=None):
    swap = db.get(models.PickSwap, swap_id)
    db.refresh(swap)
    sign_in(client, user)
    response = client.post(f"/api/swaps/join/{swap.token}", json={"wish": wish})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def group(client, db_session):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    lee = make_user(db_session, "lee")
    made = start(client, dana)
    join(client, db_session, made["id"], sam, wish="A short book")
    join(client, db_session, made["id"], lee)
    return made["id"], dana, sam, lee


def draw(client, swap_id, host):
    sign_in(client, host)
    response = client.post(f"/api/swaps/{swap_id}/draw")
    assert response.status_code == 200, response.text
    return response.json()


def target_of(client, swap_id, user):
    sign_in(client, user)
    return client.get(f"/api/swaps/{swap_id}").json()["me"]["gives_to"]["username"]


def wrap(client, swap_id, user, title="Arcane", kind="tv", **extra):
    sign_in(client, user)
    response = client.put(f"/api/swaps/{swap_id}/gift", json={"kind": kind, "title": title, "note": "Watch it", **extra})
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------- making and joining

def test_start_join_and_invite_page(client, db_session):
    dana = make_user(db_session, "dana")
    made = start(client, dana, note="Under two hours", kinds=["movie", "tv"])
    swap = db_session.get(models.PickSwap, made["id"])
    assert swap.kinds == "movie,tv" and swap.note == "Under two hours"
    assert made["invite_url"].endswith(f"/swap/join/{swap.token}")
    # The host draws by hand unless a draw day is set; unwrap day opens at 8 a.m. host time.
    assert swap.draw_on is None and swap.reveal_at.hour == 8

    sign_out(client)
    page = client.get(f"/swap/join/{swap.token}")
    assert page.status_code == 200
    assert "Office swap" in page.text and "dana" in page.text and "Join free" in page.text
    assert "noindex" in page.headers["x-robots-tag"]
    assert f"/swap/join/{swap.token}/card.png" in page.text
    assert "Films or shows" in page.text
    card = client.get(f"/swap/join/{swap.token}/card.png")
    assert card.status_code == 200 and card.content[:8] == b"\x89PNG\r\n\x1a\n"

    sam = make_user(db_session, "sam")
    sign_in(client, sam)
    preview = client.get(f"/api/swaps/join/{swap.token}").json()
    assert preview["member"] is False and preview["count"] == 1
    joined = join(client, db_session, swap.id, sam, wish="<b>Anything</b> with dragons")
    assert joined["joined"] is True and joined["path"] == f"/swap/{swap.id}"
    member = pick_swap.member_of(db_session, swap.id, sam.id)
    assert member.wish == "bAnything/b with dragons"
    note = db_session.query(models.Notification).filter_by(user_id=dana.id, type="swap_joined").one()
    assert "sam joined Office swap" in note.message
    again = client.post(f"/api/swaps/join/{swap.token}", json={})
    assert again.json()["joined"] is False


def test_bad_dates_and_names_are_refused(client, db_session):
    dana = make_user(db_session, "dana")
    sign_in(client, dana)
    today = date.today()
    for body, words in (
        ({"name": "x", "reveal_on": (today + timedelta(days=5)).isoformat()}, "name"),
        ({"name": "Swap", "reveal_on": today.isoformat()}, "after today"),
        ({"name": "Swap", "reveal_on": (today + timedelta(days=200)).isoformat()}, "within"),
        ({"name": "Swap", "reveal_on": (today + timedelta(days=5)).isoformat(),
          "draw_on": (today + timedelta(days=5)).isoformat()}, "before unwrap day"),
    ):
        response = client.post("/api/swaps", json=body)
        assert response.status_code == 422, body
        assert words in response.json()["detail"]


def test_only_members_see_a_swap(client, db_session, group):
    swap_id, dana, sam, lee = group
    stranger = make_user(db_session, "zed")
    sign_in(client, stranger)
    assert client.get(f"/api/swaps/{swap_id}").status_code == 404
    page = client.get(f"/swap/{swap_id}")
    assert "isn't here" in html.unescape(page.text)
    sign_out(client)
    page = client.get(f"/swap/{swap_id}")
    assert "Log in to see this swap" in page.text and "next=%2Fswap%2F" in page.text


# ---------------------------------------------------------------- the draw

def test_draw_is_one_loop_and_stays_secret(client, db_session, group):
    swap_id, dana, sam, lee = group
    sign_in(client, sam)
    assert client.post(f"/api/swaps/{swap_id}/draw").status_code == 403
    data = draw(client, swap_id, dana)
    assert data["state"] == "drawn" and data["givers"] == 3
    rows = db_session.query(models.PickSwapMember).filter_by(swap_id=swap_id).all()
    gives = {row.user_id: row.gives_to for row in rows}
    assert sorted(gives.values()) == sorted(gives.keys())
    assert all(giver != receiver for giver, receiver in gives.items())
    # One loop: following the arrows from anyone visits all three.
    seen, at = [], dana.id
    for _ in range(3):
        seen.append(at)
        at = gives[at]
    assert sorted(seen) == sorted(gives) and at == dana.id
    # Nobody's browser gets anyone else's draw.
    for user in (dana, sam, lee):
        sign_in(client, user)
        body = client.get(f"/api/swaps/{swap_id}").text
        mine = db_session.query(models.User).get(gives[user.id]).username
        assert f'"gives_to":{{"username":"{mine}"' in body.replace(" ", "")
        assert "board" not in client.get(f"/api/swaps/{swap_id}").json()
    notes = db_session.query(models.Notification).filter_by(type="swap_drawn").all()
    assert len(notes) == 3 and all("you're picking for" in note.message for note in notes)
    # Joining closes at the draw.
    late = make_user(db_session, "kim")
    swap = db_session.get(models.PickSwap, swap_id)
    sign_in(client, late)
    response = client.post(f"/api/swaps/join/{swap.token}", json={})
    assert response.status_code == 409 and "drawn" in response.json()["detail"]


def test_two_people_is_enough_but_one_is_not(client, db_session):
    dana = make_user(db_session, "dana")
    made = start(client, dana)
    response = client.post(f"/api/swaps/{made['id']}/draw")
    assert response.status_code == 409 and "at least 2" in response.json()["detail"]
    sam = make_user(db_session, "sam")
    join(client, db_session, made["id"], sam)
    draw(client, made["id"], dana)
    assert target_of(client, made["id"], dana) == "sam" and target_of(client, made["id"], sam) == "dana"


def test_draw_day_draws_on_its_own(client, db_session):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    today = date.today()
    made = start(client, dana, draw_on=(today + timedelta(days=1)).isoformat())
    swap = db_session.get(models.PickSwap, made["id"])
    later = swap.draw_at + timedelta(minutes=1)
    # Alone on draw day: the host hears about it once and nothing is drawn.
    result = pick_swap.advance(db_session, swap, later)
    assert result["short"] and swap.drawn_at is None
    assert pick_swap.advance(db_session, swap, later)["short"] is False
    join(client, db_session, swap.id, sam)
    db_session.refresh(swap)
    # The host was told to draw by hand, so a second person joining doesn't set off a draw of two.
    assert pick_swap.advance(db_session, swap, later)["drawn"] is False
    db_session.refresh(swap)
    assert swap.drawn_at is None
    # A new draw day starts the clock again.
    sign_in(client, dana)
    assert client.patch(f"/api/swaps/{swap.id}", json={"draw_on": (today + timedelta(days=2)).isoformat()}).status_code == 200
    db_session.refresh(swap)
    assert pick_swap.advance(db_session, swap, swap.draw_at + timedelta(minutes=1))["drawn"] is True


# ---------------------------------------------------------------- picks

def test_wrapping_a_pick_and_the_formats_rule(client, db_session):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    made = start(client, dana, kinds=["book"])
    join(client, db_session, made["id"], sam)
    draw(client, made["id"], dana)
    sign_in(client, dana)
    wrong = client.put(f"/api/swaps/{made['id']}/gift", json={"kind": "movie", "title": "Heat"})
    assert wrong.status_code == 422 and "books" in wrong.json()["detail"]
    result = wrap(client, made["id"], dana, title="Piranesi", kind="book", year=2020,
                  image="https://covers.openlibrary.org/b/id/1-L.jpg", slug="piranesi-2020")
    assert result["saved"] and result["swap"]["me"]["gift"]["title"] == "Piranesi"
    assert result["swap"]["wrapped"] == 1
    note = db_session.query(models.Notification).filter_by(user_id=sam.id, type="swap_wrapped").one()
    assert "Piranesi" not in note.message and "dana" not in note.message
    # The person who'll get it sees only that something is wrapped.
    sign_in(client, sam)
    data = client.get(f"/api/swaps/{made['id']}").json()
    assert "Piranesi" not in str(data) and "received" not in data["me"]
    # Only your own box says whose it is before unwrap day; the count says the rest.
    assert [person["wrapped"] for person in data["people"]] == [None, False] and data["wrapped"] == 1


def test_picking_something_they_have_asks_first(client, db_session):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    db_session.add(models.Movie(user_id=sam.id, title="Heat", year=1995, director="Michael Mann", watched=True))
    db_session.commit()
    made = start(client, dana)
    join(client, db_session, made["id"], sam)
    draw(client, made["id"], dana)
    sign_in(client, dana)
    response = client.put(f"/api/swaps/{made['id']}/gift", json={"kind": "movie", "title": "heat"})
    assert response.json() == {"saved": False, "has_it": True,
                               "message": "sam already has heat in their library. Pick something else, or wrap it anyway."}
    assert wrap(client, made["id"], dana, title="Heat", kind="movie", anyway=True)["saved"]
    # A private shelf is never checked, so it can't leak what's on it.
    sam_row = db_session.get(models.User, sam.id)
    sam_row.movies_private = True
    db_session.commit()
    sign_in(client, dana)
    again = client.put(f"/api/swaps/{made['id']}/gift", json={"kind": "movie", "title": "Heat"})
    assert again.json()["saved"] is True


def test_hints_come_only_from_shared_shelves(client, db_session):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam", books_private=True)
    db_session.add_all([
        models.Movie(user_id=sam.id, title="Heat", year=1995, director="", rating=9.5, watched=True),
        models.Movie(user_id=sam.id, title="Meh Film", year=2001, director="", rating=4, watched=True),
        models.Book(user_id=sam.id, title="Secret Diary", year=2001, author="", rating=10, read=True),
    ])
    db_session.commit()
    made = start(client, dana)
    join(client, db_session, made["id"], sam)
    draw(client, made["id"], dana)
    sign_in(client, dana)
    hints = client.get(f"/api/swaps/{made['id']}").json()["me"]["gives_to"]["hints"]
    assert [hint["title"] for hint in hints] == ["Heat"]


# ---------------------------------------------------------------- unwrap day

def test_unwrap_day_opens_everything(client, db_session, group):
    swap_id, dana, sam, lee = group
    draw(client, swap_id, dana)
    for user in (dana, sam):
        wrap(client, swap_id, user, title=f"Pick from {user.username}")
    sign_in(client, dana)
    early = client.post(f"/api/swaps/{swap_id}/unwrap")
    assert early.status_code == 409 and "everyone has wrapped" in early.json()["detail"]
    swap = db_session.get(models.PickSwap, swap_id)
    # Two days out: a reminder for whoever hasn't picked.
    pick_swap.advance(db_session, swap, swap.reveal_at - timedelta(days=1))
    reminder = db_session.query(models.Notification).filter_by(type="swap_reminder").all()
    assert [note.user_id for note in reminder] == [lee.id]
    pick_swap.advance(db_session, swap, swap.reveal_at + timedelta(minutes=5))
    db_session.refresh(swap)
    assert swap.revealed_at is not None
    gives = {row.user_id: row.gives_to for row in db_session.query(models.PickSwapMember).filter_by(swap_id=swap_id)}
    lee_target = gives[lee.id]
    late = db_session.query(models.Notification).filter_by(type="swap_late", user_id=lee.id).one()
    assert "waiting on your pick" in late.message
    sign_in(client, db_session.get(models.User, lee_target))
    data = client.get(f"/api/swaps/{swap_id}").json()
    assert data["state"] == "revealed" and data["me"]["received"] == {"from": "lee", "pending": True}
    assert len(data["board"]) == 3
    # A late pick still lands after unwrap day, once.
    wrap(client, swap_id, lee, title="Late pick")
    sign_in(client, lee)
    changed = client.put(f"/api/swaps/{swap_id}/gift", json={"kind": "tv", "title": "Another"})
    assert changed.status_code == 409


def test_opening_adding_and_thanking(client, db_session):
    dana = make_user(db_session, "dana")
    sam = make_user(db_session, "sam")
    made = start(client, dana)
    join(client, db_session, made["id"], sam)
    draw(client, made["id"], dana)
    wrap(client, made["id"], dana, title="Arcane", kind="tv", year=2021,
         image="https://image.tmdb.org/t/p/w342/arcane.jpg", slug="arcane-2021")
    wrap(client, made["id"], sam, title="Dune", kind="book")
    sign_in(client, dana)
    data = client.post(f"/api/swaps/{made['id']}/unwrap").json()
    assert data["state"] == "revealed"
    sign_in(client, sam)
    received = client.get(f"/api/swaps/{made['id']}").json()["me"]["received"]
    assert received["title"] == "Arcane" and received["from"] == "dana" and received["opened"] is False
    assert received["url"] == "/titles/tv/arcane-2021"
    assert client.post(f"/api/swaps/{made['id']}/received/open").json() == {"first": True}
    assert client.post(f"/api/swaps/{made['id']}/received/open").json() == {"first": False}
    added = client.post(f"/api/swaps/{made['id']}/received/add", json={"queue": True}).json()
    assert added["created"] and added["queued"] and added["category"] == "tv-shows"
    show = db_session.query(models.TVShow).filter_by(user_id=sam.id, title="Arcane").one()
    assert show.poster_url == "https://image.tmdb.org/t/p/w342/arcane.jpg"
    origin = db_session.query(models.TitleOrigin).filter_by(user_id=sam.id, item_id=show.id).one()
    assert origin.who == "dana" and "Pick swap" in origin.note
    assert db_session.query(models.NextUpItem).filter_by(user_id=sam.id, item_id=show.id).count() == 1
    # Adding again doesn't make a second copy or a second note to the giver.
    client.post(f"/api/swaps/{made['id']}/received/add", json={})
    assert db_session.query(models.TVShow).filter_by(user_id=sam.id, title="Arcane").count() == 1
    assert db_session.query(models.Notification).filter_by(user_id=dana.id, type="swap_added").count() == 1
    thanked = client.post(f"/api/swaps/{made['id']}/received/thanks", json={"reaction": "love"})
    assert thanked.status_code == 200
    assert client.post(f"/api/swaps/{made['id']}/received/thanks", json={"reaction": "nope"}).status_code == 422
    client.post(f"/api/swaps/{made['id']}/received/thanks", json={"reaction": "perfect"})
    notes = db_session.query(models.Notification).filter_by(user_id=dana.id, type="swap_thanks").all()
    assert len(notes) == 1 and "Love it" in notes[0].message
    sign_in(client, dana)
    board = client.get(f"/api/swaps/{made['id']}").json()["board"]
    assert {entry["thanks"] for entry in board} == {"Perfect pick", ""}


def test_nothing_opens_before_unwrap_day(client, db_session, group):
    swap_id, dana, sam, lee = group
    draw(client, swap_id, dana)
    sign_in(client, sam)
    for path in ("received/open", "received/add", "received/thanks"):
        body = {"reaction": "love"} if path.endswith("thanks") else {}
        response = client.post(f"/api/swaps/{swap_id}/{path}", json=body)
        assert response.status_code == 409, path


# ---------------------------------------------------------------- people leaving

def test_leaving_after_the_draw_steps_over(client, db_session, group):
    swap_id, dana, sam, lee = group
    draw(client, swap_id, dana)
    gives = {row.user_id: row.gives_to for row in db_session.query(models.PickSwapMember).filter_by(swap_id=swap_id)}
    giver_of_sam = next(user for user, target in gives.items() if target == sam.id)
    giver_user = db_session.get(models.User, giver_of_sam)
    wrap(client, swap_id, giver_user, title="For sam")
    sign_in(client, sam)
    assert client.post(f"/api/swaps/{swap_id}/leave").json() == {"left": True, "swap_kept": True}
    db_session.expire_all()
    row = pick_swap.member_of(db_session, swap_id, giver_of_sam)
    assert row.gives_to == gives[sam.id] and row.picked_at is None
    note = db_session.query(models.Notification).filter_by(user_id=giver_of_sam, type="swap_drawn").order_by(
        models.Notification.id.desc()).first()
    assert "sam left" in note.message and "pick again" in note.message
    # Down to two, then one: the swap is called off.
    other = lee if giver_of_sam == dana.id else dana
    sign_in(client, other)
    result = client.post(f"/api/swaps/{swap_id}/leave").json()
    db_session.expire_all()
    swap = db_session.get(models.PickSwap, swap_id)
    if other.id == dana.id:
        assert swap.owner_id == lee.id
    assert result["swap_kept"] is False and swap.cancelled_at is not None


def test_host_takes_someone_out_and_the_link_wont_add_them_back(client, db_session, group):
    swap_id, dana, sam, lee = group
    member = pick_swap.member_of(db_session, swap_id, sam.id)
    sign_in(client, lee)
    assert client.delete(f"/api/swaps/{swap_id}/members/{member.id}").status_code == 403
    sign_in(client, dana)
    data = client.delete(f"/api/swaps/{swap_id}/members/{member.id}").json()
    assert [person["username"] for person in data["people"]] == ["dana", "lee"]
    swap = db_session.get(models.PickSwap, swap_id)
    sign_in(client, sam)
    response = client.post(f"/api/swaps/join/{swap.token}", json={})
    assert response.status_code == 403
    assert "took you out" in html.unescape(client.get(f"/swap/join/{swap.token}").text)


def test_deactivated_member_is_stepped_over(client, db_session, group):
    swap_id, dana, sam, lee = group
    draw(client, swap_id, dana)
    sam_row = db_session.get(models.User, sam.id)
    sam_row.is_active = False
    db_session.commit()
    sign_in(client, dana)
    data = client.get(f"/api/swaps/{swap_id}").json()
    assert data["givers"] == 2 and data["me"]["gives_to"]["username"] == "lee"
    sign_in(client, lee)
    assert client.get(f"/api/swaps/{swap_id}").json()["me"]["gives_to"]["username"] == "dana"


def test_host_edits_and_calls_off(client, db_session, group):
    swap_id, dana, sam, lee = group
    sign_in(client, sam)
    assert client.patch(f"/api/swaps/{swap_id}", json={"name": "Mine now"}).status_code == 403
    sign_in(client, dana)
    later = (date.today() + timedelta(days=20)).isoformat()
    data = client.patch(f"/api/swaps/{swap_id}", json={"name": "Family picks", "reveal_on": later,
                                                         "kinds": ["album"]}).json()
    assert data["name"] == "Family picks" and data["reveal_on"] == later and data["kinds"] == ["album"]
    old = db_session.get(models.PickSwap, swap_id).token
    fresh = client.post(f"/api/swaps/{swap_id}/link").json()
    assert old not in fresh["invite_url"]
    sign_out(client)
    assert "doesn't work anymore" in html.unescape(client.get(f"/swap/join/{old}").text)
    sign_in(client, dana)
    assert client.post(f"/api/swaps/{swap_id}/cancel").json() == {"cancelled": True}
    assert db_session.query(models.Notification).filter_by(type="swap_off").count() == 2
    assert client.get("/api/swaps").json()["swaps"] == []


# ---------------------------------------------------------------- the hub, home card and emails

def test_my_swaps_says_what_to_do_next(client, db_session, group):
    swap_id, dana, sam, lee = group
    sign_in(client, sam)
    line = client.get("/api/swaps").json()["swaps"][0]
    assert line["state"] == "open" and "3 people in" in line["line"]
    draw(client, swap_id, dana)
    sign_in(client, sam)
    line = client.get("/api/swaps").json()["swaps"][0]
    target = target_of(client, swap_id, sam)
    assert line["urgent"] and line["action"]["label"] == f"Pick for {target}"
    wrap(client, swap_id, sam, title="Dune", kind="book")
    sign_in(client, sam)
    line = client.get("/api/swaps").json()["swaps"][0]
    assert not line["urgent"] and line["line"].startswith(f"You wrapped Dune for {target}")


def test_emails_go_once_each_and_respect_the_opt_out(client, db_session, group, monkeypatch):
    from tests.conftest import TestingSessionLocal
    swap_id, dana, sam, lee = group
    db_session.add(models.EmailOptOut(user_id=lee.id))
    db_session.commit()
    draw(client, swap_id, dana)
    sent = []

    async def sender(to, subject, body, unsubscribe):
        sent.append((to, subject, body))

    monkeypatch.setattr(pick_swap, "allowance", lambda db, now: 10)
    now = datetime.utcnow()
    result = asyncio.run(pick_swap.run_once(TestingSessionLocal, now=now, sender=sender))
    assert result["sent"] == 2
    assert {to for to, *_ in sent} == {"dana@example.test", "sam@example.test"}
    assert all(subject.startswith("You're picking for") for _to, subject, _html in sent)
    giver_of_sam = pick_swap.giver_of(db_session, swap_id, sam.id).user_id
    if giver_of_sam != lee.id:  # sam's wish reaches whoever drew sam (lee opted out of emails)
        email = next(body for to, _subject, body in sent if to == db_session.get(models.User, giver_of_sam).email)
        assert "A short book" in email
    asyncio.run(pick_swap.run_once(TestingSessionLocal, now=now + timedelta(minutes=15), sender=sender))
    assert len(sent) == 2
    # Unwrap day: one email per person whose pick is wrapped.
    for user in (dana, sam, lee):
        wrap(client, swap_id, user, title=f"From {user.username}")
    sent.clear()
    swap = db_session.get(models.PickSwap, swap_id)
    later = swap.reveal_at + timedelta(minutes=1)
    asyncio.run(pick_swap.run_once(TestingSessionLocal, now=later, sender=sender))
    subjects = sorted(subject for _to, subject, _html in sent)
    assert len(subjects) == 2 and all("ready to unwrap" in subject for subject in subjects)
    assert all("From " not in body for _to, _subject, body in sent)  # the title stays a surprise


def test_wiring(client):
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    from app.main import PICK_SWAP_LIMITS
    from app.routers import pick_swap as router
    api_routes = {(route.path, method) for route in router.router.routes for method in route.methods
                  if route.path.startswith("/api/")}
    assert api_routes <= set(PICK_SWAP_LIMITS), api_routes - set(PICK_SWAP_LIMITS)
    assert "pick_swap.swap_loop" in main
    from app import site_traffic
    assert site_traffic.PRIVATE_LINK.match("/swap/join/abcdefghijklmnop")
    auth_js = (ROOT / "app" / "static" / "auth.js").read_text(encoding="utf-8")
    assert "\\/swap(?:\\/join\\/[A-Za-z0-9_-]{16,40}|\\/([1-9]\\d{0,9}))?$" in auth_js
    index = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="swapHome"' in index and "/static/pick-swap-home.js?v=" in index
    guide = client.get("/swap")
    assert guide.status_code == 200 and "How to run a recommendation swap" in guide.text
    assert "index, follow" in guide.text
    assert "/swap" in client.get("/sitemap.xml").text
