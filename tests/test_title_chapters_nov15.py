"""Title pages, Nov 15 2026: chapters below the hero (sidebar beside the reviews only, where to watch
beside the trailer, cast and crew, one review/discussion panel, poster rails, the guest join band)."""
from app import funnel, title_metadata
from app.routers import titles
from tests.test_title_detail_redesign import WHERE
from tests.test_title_pages import ESSAY, SAMPLE, add_movie, member, seed_metadata

CAST = {**SAMPLE, "facts": [{"label": "Director", "value": "Christopher Nolan"},
                            {"label": "Starring", "value": "Matthew McConaughey, Anne Hathaway, Jessica Chastain, Michael Caine"},
                            {"label": "Running time", "value": "169 min"}]}


def page(client, db_session, data=SAMPLE, where=WHERE, review=False, count=1):
    for index in range(count):
        add_movie(db_session, member(db_session, f"fan{index}"), rating=9, watched=True,
                  review=ESSAY if review and index == 0 else None, review_public=review and index == 0)
    db_session.commit()
    seed_metadata(db_session, data)
    if where is not None:
        title_metadata.store(db_session, "where:movie:interstellar:2014", where, "ok")
    response = client.get("/titles/movie/interstellar-2014")
    assert response.status_code == 200
    return response.text


def between(html, start, end="</section>"):
    return html.split(start, 1)[1].split(end, 1)[0]


def test_where_to_watch_sits_beside_the_trailer(client, db_session):
    html = page(client, db_session)
    pair = between(html, '<div class="title-pair">', '<section class="title-section title-about"')
    assert 'id="where-title"' in pair and 'id="trailer-title"' in pair
    # The pair shares one tab, and the hero has a one-tap trailer button.
    assert '<a href="#trailer-title">Trailer</a>' not in html and '<a href="#where-title">' in html
    assert 'href="#trailer-title" data-trailer-jump>' in html


def test_without_providers_the_trailer_stands_alone(client, db_session):
    html = page(client, db_session, where=None)
    assert 'class="title-pair"' not in html and 'id="trailer-title"' in html


def test_reviews_lead_and_the_rest_follows(client, db_session):
    html = page(client, db_session, review=True, count=3)
    lead = between(html, 'class="title-main title-main--lead"', 'class="title-main title-main--rest"')
    assert 'id="community-title"' in lead and "Read the full review" in lead and 'id="write-review"' not in lead
    assert 'class="title-scorecard' in lead and "Member score" in lead
    rest = html.split('class="title-main title-main--rest"', 1)[1]
    assert rest.index('id="where-title"') < rest.index('id="about-title"') < rest.index('id="faq-title"') < rest.index('id="write-review"')
    # The Nov 15 sidebar repeated the score a third time; the scorecard replaced it on Nov 20.
    assert "glance-title" not in html


def test_no_reviews_yet_puts_the_review_prompt_by_the_numbers(client, db_session):
    html = page(client, db_session, count=3)
    lead = between(html, 'class="title-main title-main--lead"', 'class="title-main title-main--rest"')
    assert "No public reviews yet" not in html and "Member reviews" not in lead
    assert "Be the first to review Interstellar" in lead and "Nobody has started a discussion about Interstellar yet" in lead
    # The tabs follow the page: discussions come straight after reviews.
    nav = between(html, 'aria-label="On this page">', "</nav>")
    assert nav.index("#community-title") < nav.index("#discussions-title") < nav.index("#where-title")


def test_cast_and_crew_fill_about_and_replace_the_starring_row(client, db_session):
    html = page(client, db_session, data=CAST)
    about = between(html, 'class="title-section title-about"')
    assert 'class="title-cast title-cast--nested"' in about and 'id="cast-title"' in about
    for name in ("Christopher Nolan", "Matthew McConaughey", "Michael Caine"):
        assert f"<strong>{name}</strong>" in about
    assert "<small>Director</small>" in about and "<small>Cast</small>" in about
    assert "<dt>Starring</dt>" not in about and "<dt>Director</dt>" in about
    assert '<a href="#cast-title">Cast and crew</a>' in html
    # Initials, with a steady colour per name.
    assert ">CN</span>" in about and titles._hue("Christopher Nolan") == titles._hue("Christopher Nolan")


def test_short_credits_skip_the_cast_strip(client, db_session):
    html = page(client, db_session)
    assert 'id="cast-title"' not in html and "<dt>Director</dt>" in html


def test_cast_helpers():
    assert titles._initials("Joseph Gordon-Levitt") == "JL"
    assert titles._initials("Zendaya") == "Z"
    assert titles._initials("") == "?"


def test_guest_join_band_and_rails(client, db_session):
    html = page(client, db_session)
    band = between(html, '<section class="title-join')
    assert "Keep Interstellar on a list that goes everywhere with you" in band
    assert 'href="/#signup" data-title-signup>Create a free account</a>' in band
    assert "data-join-save>Save Interstellar first</button>" in band
    # The band presses the hero button; the hero button stays the only one that saves.
    assert html.count("data-guest-save") == 1
    assert {"title_signup_clicked", "title_trailer_played"} <= funnel.CLIENT_EVENTS
    assert titles._rail("<a>x</a>") == '<div class="title-rail" data-title-rail><div class="title-related-grid"><a>x</a></div></div>'


def test_members_get_no_join_band(client, db_session):
    client.cookies.set("omnitrackr_session", "anything")
    html = page(client, db_session)
    assert 'class="title-join' not in html and "data-join-save" not in html
