"""Homepage "Start your library": format chips, the "Your library" panel and its suggestions (Nov 22 2026)."""
from pathlib import Path

from app import funnel, guest_picks, landing_proof, main, models

ROOT = Path(__file__).resolve().parents[1]


def item(kind, title, year, image="https://img.example/p.jpg"):
    slug = f"{title.lower().replace(' ', '-')}-{year}"
    labels = {"movie": "Movie", "game": "Video game", "tv": "TV show"}
    return {"kind": kind, "title": title, "year": year, "url": f"/titles/{kind}/{slug}", "label": labels[kind],
            "image": image, "members": 3}


def test_chips_show_more_of_one_kind_and_the_panel_sits_beside_the_picks():
    movies = [item("movie", f"Film {n}", 2000 + n) for n in range(7)]
    games = [item("game", f"Game {n}", 2010 + n) for n in range(3)]
    top = movies[:4] + games[:2]
    html = guest_picks.section_html(top, {"movie": movies, "game": games})
    # Movies have enough titles for a chip; three games don't.
    assert 'data-picks-filter="top"' in html and 'data-picks-filter="movie"' in html
    assert 'data-picks-filter="game"' not in html
    # The mixed set shows; the other films wait for their chip, and no title is drawn twice.
    assert html.count("data-picks-top") == 6
    assert html.count('data-picks-kind="movie" hidden') == 3
    assert html.count('data-guest-slug="film-0-2000"') == 1
    assert 'data-guest-shelf' in html and html.count('class="lp-shelf__slot"') == guest_picks.SHELF_SLOTS
    assert "<!--SHELF_SIGNUP-->" in html and 'data-picks-search' in html
    # Without per-kind lists there are no chips at all.
    assert "data-picks-filter" not in guest_picks.section_html(top)
    assert guest_picks.section_html(top[:5]) == ""


def test_section_escapes_titles():
    evil = [item("movie", f"Film {n}", 2000 + n) for n in range(6)]
    evil[0] = {**evil[0], "title": '<img src=x onerror=alert(1)>'}
    html = guest_picks.section_html(evil, {"movie": evil})
    assert "<img src=x" not in html and "&lt;img src=x" in html


def test_panel_buttons_follow_google_sign_in():
    with_google = main.shelf_signup_html(True)
    assert 'href="/auth/google/start"' in with_google and "data-google-signup" in with_google
    assert with_google.count("data-shelf-signup") == 2 and 'data-action="show-register-form"' in with_google
    without = main.shelf_signup_html(False)
    assert "google" not in without.lower() and "Create a free account" in without


def test_homepage_fills_the_panel_buttons(client, db_session, monkeypatch):
    movies = [item("movie", f"Film {n}", 2000 + n) for n in range(8)]
    monkeypatch.setattr(guest_picks, "homepage_section", lambda: guest_picks.section_html(movies, {"movie": movies}))
    page = client.get("/").text
    assert "data-guest-shelf" in page and "SHELF_SIGNUP" not in page
    assert "/static/home-shelf.js?v=" in page and page.index("guest-list.js") < page.index("home-shelf.js")
    assert "data-savebar-covers" in page


def seed_three_members(db, private_one=False):
    users = [models.User(username=f"s{i}", email=f"s{i}@example.com", hashed_password="x", is_verified=True,
                         movies_private=(private_one and i == 2)) for i in range(3)]
    db.add_all(users)
    db.flush()
    for user in users:
        for title, year in (("Arrival", 2016), ("Heat", 1995)):
            db.add(models.Movie(user_id=user.id, title=title, director="x", year=year, poster_url="https://img.example/a.jpg"))
    for user in users[:2]:
        db.add(models.TVShow(user_id=user.id, title="Severance", year=2022))
    db.add(models.TVShow(user_id=users[2].id, title="Only Mine", year=2020))
    db.commit()
    return users


def test_suggestions_are_what_members_who_track_it_also_track(db_session):
    seed_three_members(db_session)
    results = guest_picks.suggestions(db_session, "movie", "arrival-2016")
    pairs = {(entry["kind"], entry["slug"]) for entry in results}
    assert ("movie", "heat-1995") in pairs and ("tv", "severance-2022") in pairs
    # One member's title never shows, and the title asked about isn't suggested back.
    assert ("tv", "only-mine-2020") not in pairs and ("movie", "arrival-2016") not in pairs
    assert set(results[0]) == {"kind", "slug", "title", "label", "year", "image"}


def test_suggestions_skip_private_shelves_and_bad_input(db_session):
    seed_three_members(db_session, private_one=True)
    # Two members can still share Arrival, but the third keeps films private and isn't counted.
    assert all(entry["slug"] != "only-mine-2020" for entry in guest_picks.suggestions(db_session, "movie", "arrival-2016"))
    assert guest_picks.suggestions(db_session, "movie", "Not A Slug") == []
    assert guest_picks.suggestions(db_session, "comic", "arrival-2016") == []
    assert guest_picks.suggestions(db_session, "movie", "nobody-tracks-this-1999") == []


def test_suggest_endpoint_is_public_and_cacheable(client, db_session):
    seed_three_members(db_session)
    response = client.get("/api/guest-list/suggest", params={"kind": "movie", "slug": "arrival-2016"})
    assert response.status_code == 200
    assert "public" in response.headers["cache-control"]
    assert any(entry["slug"] == "heat-1995" for entry in response.json()["results"])
    assert client.get("/api/guest-list/suggest", params={"kind": "movie", "slug": "x" * 200}).status_code == 422
    assert client.get("/api/guest-list/suggest", params={"kind": "movie"}).status_code == 422


def test_homepage_quotes_only_english_reviews():
    english = "Warmer than I expected. The film lets the quieter scenes breathe and the final act is noisy but fun."
    spanish = "La historia es mala y por eso el final es malo, los protagonistas son tontísimos y solo los secundarios son buenos"
    polish = "Bardzo miłe zaskoczenie. Gra ma niepowtarzalny klimat, całkiem dobrą historię, świetne postacie i świat oraz fajny humor."
    assert landing_proof.reads_as_english(english)
    assert not landing_proof.reads_as_english(spanish) and not landing_proof.reads_as_english(polish)
    reviews = [{"id": n, "user_id": n, "category": "movie", "title": f"T{n}", "search_ready": True, "review": text}
               for n, text in enumerate((spanish, english, polish))]
    assert [review["id"] for review in landing_proof.pick_reviews(reviews)] == [1]


def test_new_homepage_moments_are_counted():
    labels = dict(funnel.GUEST)
    for event in ("home_picks_filtered", "home_shelf_suggestion_added", "home_shelf_signup"):
        assert event in funnel.CLIENT_EVENTS and event in labels


def test_streaming_card_replaces_the_tier_list_card(client):
    html = client.get("/").text
    features = html[html.index('id="features"'):]
    features = features[:features.index("</section>")]
    assert "What’s on the services you have" in features and "24 US services" in features
    assert "Rank anything from S to D" not in features
    tools = html[html.index('id="free-tools"'):]
    assert 'href="/tier-list"' in tools[:tools.index("</section>")]


def test_panel_script_never_writes_html():
    source = (ROOT / "app/static/home-shelf.js").read_text(encoding="utf-8")
    assert "innerHTML" not in source and "insertAdjacentHTML" not in source
