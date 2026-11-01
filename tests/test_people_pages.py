"""People and studio pages: credits, member numbers, indexing rules and links from title pages."""
from app import auth, models, people_pages, title_metadata
from app.editorial_collections import EDITOR_EMAIL, EDITOR_USERNAME

REVIEW = (
    "The pacing is patient in a way most films this size never risk, and the last half hour pays every minute back. "
    "The score carries scenes the dialogue cannot, and the lead performance holds the whole thing together. I have "
    "watched it three times now and still notice new small choices in how the scenes are framed and cut."
)


def member(db, name, **extra):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password=auth.get_password_hash("password123"),
                       is_verified=True, is_active=True, **extra)
    db.add(user)
    db.flush()
    return user


def movie(db, user, title, year, director="Christopher Nolan", **extra):
    row = models.Movie(user_id=user.id, title=title, year=year, director=director, **extra)
    db.add(row)
    db.flush()
    return row


def facts(db, key, *pairs):
    title_metadata.store(db, key, {"facts": [{"label": label, "value": value} for label, value in pairs]}, "ok")


def nolan_library(db):
    users = [member(db, f"m{i}") for i in range(4)]
    for index, user in enumerate(users):
        movie(db, user, "Interstellar", 2014, rating=9.0 - index * 0.2,
              review=REVIEW if index < 2 else None, review_public=index < 2)
        movie(db, user, "The Prestige", 2006, rating=7.0 + index * 0.1)
        if index < 2:
            movie(db, user, "Tenet", 2020, rating=6.0, review=REVIEW + " Tenet is the odd one out.", review_public=index == 0)
    db.commit()
    return users


def test_split_names_keeps_company_suffixes_and_bands():
    assert people_pages.split_names("Phil Lord, Christopher Miller", "Director") == ["Phil Lord", "Christopher Miller"]
    assert people_pages.split_names("Square Enix Co., Ltd.", "Developer") == ["Square Enix Co., Ltd."]
    assert people_pages.split_names("Earth, Wind & Fire", "Artist") == ["Earth, Wind & Fire"]
    assert people_pages.split_names("  ", "Director") == []


def test_storing_facts_indexes_credits_and_replaces_them(db_session):
    facts(db_session, "movie:interstellar:2014", ("Director", "Christopher Nolan"),
          ("Starring", "Matthew McConaughey, Anne Hathaway"), ("Studio", "Syncopy"), ("Country", "United States"))
    rows = {(c.entity, c.role, c.slug) for c in db_session.query(models.TitleCredit)}
    assert rows == {("person", "Director", "christopher-nolan"), ("person", "Cast", "matthew-mcconaughey"),
                    ("person", "Cast", "anne-hathaway"), ("studio", "Studio", "syncopy")}
    facts(db_session, "movie:interstellar:2014", ("Director", "Christopher Nolan"))
    assert db_session.query(models.TitleCredit).count() == 1
    # A failed refresh keeps the last good facts and their credits.
    title_metadata.store(db_session, "movie:interstellar:2014", None, "error")
    assert db_session.query(models.TitleCredit).count() == 1


def test_backfill_indexes_facts_cached_before_credits(db_session):
    db_session.add(models.TitleMetadata(key="anime:frieren:2023", status="ok",
                                        data='{"facts": [{"label": "Studio", "value": "Madhouse"}]}'))
    db_session.commit()
    assert people_pages.backfill(db_session) == 1
    credit = db_session.query(models.TitleCredit).one()
    assert (credit.entity, credit.slug, credit.kind) == ("studio", "madhouse", "anime")
    assert people_pages.backfill(db_session) == 0


def test_person_page_ranks_work_by_member_rating(client, db_session):
    nolan_library(db_session)
    response = client.get("/people/christopher-nolan")
    assert response.status_code == 200
    html = response.text
    assert "<h1>Christopher Nolan</h1>" in html
    assert "OmniTrackr members track 3 movies directed by Christopher Nolan." in html
    assert "Members rate Interstellar highest" in html
    assert html.index('href="/titles/movie/interstellar-2014"') < html.index('href="/titles/movie/the-prestige-2006"')
    assert "What members wrote" in html and "Read the full review" in html
    # Tenet has two ratings, below the three a title needs to be ranked.
    assert "1 more needs 3 member ratings to be ranked" in html
    # Three titles, two ranked, three reviews with enough words: offered to search.
    assert 'content="index, follow' in html and "X-Robots-Tag" not in response.headers


def test_thin_person_page_stays_out_of_search(client, db_session):
    user = member(db_session, "solo")
    movie(db_session, user, "Memento", 2000)
    db_session.commit()
    response = client.get("/people/christopher-nolan")
    assert response.status_code == 200
    assert response.headers["X-Robots-Tag"] == "noindex, follow"
    assert "ad-loader.js" not in response.text
    assert client.get("/people/nobody-at-all").status_code == 404
    assert client.get("/people/..%2Fetc").status_code == 404


def test_private_categories_and_editors_are_left_out(client, db_session):
    hidden = member(db_session, "hidden", movies_private=True)
    movie(db_session, hidden, "Following", 1998)
    editor = models.User(username=EDITOR_USERNAME, email=EDITOR_EMAIL, hashed_password="x", is_verified=True, is_active=True)
    db_session.add(editor)
    db_session.flush()
    movie(db_session, editor, "Insomnia", 2002)
    db_session.commit()
    assert client.get("/people/christopher-nolan").status_code == 404


def test_studio_page_from_cached_credits(client, db_session):
    users = [member(db_session, f"a{i}") for i in range(3)]
    for user in users:
        for title, year in (("Frieren", 2023), ("Parasyte", 2014)):
            db_session.add(models.Anime(user_id=user.id, title=title, year=year, rating=8.0))
    db_session.commit()
    facts(db_session, "anime:frieren:2023", ("Studio", "Madhouse"), ("Director", "Keiichiro Saito"))
    facts(db_session, "anime:parasyte:2014", ("Studio", "Madhouse"))
    response = client.get("/studios/madhouse")
    assert response.status_code == 200
    assert "OmniTrackr members track 2 anime from Madhouse." in response.text
    assert 'href="/people/keiichiro-saito"' in response.text  # credited alongside
    assert client.get("/people/madhouse").status_code == 404


def test_title_page_links_credits_with_pages(client, db_session):
    nolan_library(db_session)
    facts(db_session, "movie:interstellar:2014", ("Director", "Christopher Nolan"), ("Starring", "Michael Caine, Jessica Chastain"))
    facts(db_session, "movie:the prestige:2006", ("Director", "Christopher Nolan"), ("Starring", "Michael Caine"))
    html = client.get("/titles/movie/interstellar-2014").text
    assert '<a href="/people/christopher-nolan">Christopher Nolan</a>' in html
    assert '<a href="/people/michael-caine">Michael Caine</a>' in html
    # One credited title is not worth a page of its own, so no link.
    assert 'href="/people/jessica-chastain"' not in html and "Jessica Chastain" in html
    assert "Every Christopher Nolan title, ranked" in html


def test_directories_list_names_with_several_titles(client, db_session):
    nolan_library(db_session)
    facts(db_session, "game:hades:2020", ("Developer", "Supergiant Games"))
    facts(db_session, "game:bastion:2011", ("Developer", "Supergiant Games"))
    people = client.get("/people")
    assert people.status_code == 200 and 'href="/people/christopher-nolan"' in people.text
    assert people.headers["X-Robots-Tag"] == "noindex, follow"
    studios = client.get("/studios").text
    assert 'href="/studios/supergiant-games"' in studios and "Game developers" in studios


def test_sitemap_lists_indexable_people(db_session):
    nolan_library(db_session)
    assert people_pages.sitemap_paths(db_session) == ["/people/christopher-nolan"]
