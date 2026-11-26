"""Title pages, Nov 25 2026: an "in our guides" section linking to the written guides that mention
the title, and a quieter sign-up button on the member scorecard."""
from tests.test_title_chapters_nov15 import between
from tests.test_title_pages import add_movie, member


def _arrival(client, db_session, title="Arrival", year=2016):
    add_movie(db_session, member(db_session, "fan0"), title=title, year=year, rating=9, watched=True)
    db_session.commit()
    response = client.get(f"/titles/movie/{title.lower()}-{year}")
    assert response.status_code == 200
    return response.text


def test_title_page_links_the_guides_that_mention_it(client, db_session):
    html = _arrival(client, db_session)
    section = between(html, '<section class="title-section title-guides"', "</section>")
    assert '<h2 id="guides-title">Arrival in our guides</h2>' in section
    assert '<a class="title-guides__link" href="/if-you-liked/interstellar">If you liked Interstellar</a>' in section
    assert '<p class="title-guides__section">If you liked</p>' in section
    # It has a stop in the tabs.
    assert 'href="#guides-title"' in html


def test_guides_already_linked_above_are_not_repeated(client, db_session):
    html = _arrival(client, db_session, title="Interstellar", year=2014)
    # The If you liked guide about Interstellar has its own section; the guides list doesn't repeat it.
    assert 'href="/if-you-liked/interstellar">If you liked Interstellar →</a>' in html
    assert 'class="title-guides__link" href="/if-you-liked/interstellar"' not in html


def test_scorecard_sign_up_is_an_outline_button(client, db_session):
    html = _arrival(client, db_session)
    assert '<a class="site-btn site-btn--ghost site-btn--sm" href="/#signup" data-title-signup>Start your free library</a>' in html
