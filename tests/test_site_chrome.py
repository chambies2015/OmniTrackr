"""Shared public header/footer and the redesigned Guides, Reviews and Discover pages."""
import re

import pytest

from app import crud, models, site_chrome
from app.schemas import MovieCreate

LONG_REVIEW = (
    "The film builds its tension slowly, trusting quiet scenes and a patient score before the final act. "
    "Its lead performance carries the uncertainty well, and the second half rewards anyone who stays with it. "
    "I would recommend it to viewers who like character studies more than twists, and would watch it again."
)

GUIDE_PAGES = ["/guides", "/media-tracking", "/export-import-guide", "/review-guidelines", "/sample-library",
               "/movie-tracker", "/tv-show-tracker", "/anime-tracker", "/game-tracker", "/music-tracker",
               "/book-tracker", "/media-statistics", "/media-tracker-checklist", "/tracking-templates",
               "/compare", "/use-cases"]
CHROME_PAGES = {"/": "", "/discover": "discover", "/discover/finding-your-feet": "discover",
                "/reviews": "reviews", "/release-radar": "release-radar", "/collections/explore": "collections",
                "/faq": "faq", "/about": "", "/privacy": "", "/terms": "", "/contact": "", "/changelog": "",
                "/roadmap": "", "/site-map": "", "/content-quality": "", "/advertising": "", "/demo": "",
                **{path: "guides" for path in GUIDE_PAGES}}


def current_nav_key(html):
    header = html[html.index('<header class="site-header">'):html.index("</header>")]
    match = re.search(r'class="site-nav__link [^"]*" href="([^"]+)" aria-current="page"', header)
    return match.group(1) if match else ""


@pytest.mark.parametrize("path, active", sorted(CHROME_PAGES.items()))
def test_pages_share_one_header_and_footer(client, path, active):
    html = client.get(path).text
    assert "<!--SITE_" not in html
    assert html.count('<header class="site-header">') == 1
    assert html.count('<footer class="site-footer">') == 1
    assert "/static/site.css?v=" in html and "/static/site.js?v=" in html
    expected = dict((key, href) for key, _, href in site_chrome.NAV_ITEMS).get(active, "")
    assert current_nav_key(html) == expected
    footer = html[html.index('<footer class="site-footer">'):]
    for _, links in site_chrome.FOOTER_GROUPS:
        for _, href in links:
            assert f'href="{href}"' in footer


def test_guide_pages_use_the_dark_reader_theme(client):
    for path in GUIDE_PAGES:
        html = client.get(path).text
        assert '<body class="public-reader site">' in html, path
        assert 'class="reader-nav-wrap"' not in html and 'class="reader-footer"' not in html
    css = client.get("/static/public-reader.css").text
    assert "var(--site-bg)" in css and "prefers-color-scheme" not in css


def test_chrome_helper_is_idempotent_and_leaves_other_pages_alone():
    assert site_chrome.apply_site_chrome("<html><head></head><body>x</body></html>") == "<html><head></head><body>x</body></html>"
    page = "<html><head></head><body><!--SITE_NAV:reviews--><!--SITE_FOOTER--></body></html>"
    once = site_chrome.apply_site_chrome(page)
    assert once.count("/static/site.css") == 1
    assert site_chrome.apply_site_chrome(once) == once
    assert 'data-action="show-login-form"' not in once
    assert 'data-action="show-login-form"' in site_chrome.apply_site_chrome(page, login_action=True)


def test_review_category_chip_marks_the_current_filter(client):
    html = client.get("/reviews?category=anime").text
    assert '<a href="/reviews?category=anime" aria-current="page">' in html
    assert 'aria-current="page">' not in client.get("/reviews").text.split('reviews-category-nav')[1].split('</nav>')[0]


def test_review_detail_redesign_with_related_reviews(client, db_session, authenticated_client, test_user_data):
    user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
    first = crud.create_movie(db_session, user.id, MovieCreate(title="First Film", director="A", year=2024,
                                                              review=LONG_REVIEW, review_public=True, rating=8))
    crud.create_movie(db_session, user.id, MovieCreate(title="Second Film", director="B", year=2025,
                                                       review=LONG_REVIEW, review_public=True))
    db_session.commit()
    client.headers = {}
    html = client.get(f"/reviews/{first.id}?category=movie").text
    assert 'class="review-hero"' in html and "Reviewed by <strong>testuser</strong>" in html
    assert "/static/review-detail.css" in html and "<style>" not in html
    assert 'href="/reviews/%d/save?category=movie"' % first.id in html
    more = html[html.index('class="review-more'):]
    assert "More movie reviews" in more and "Second Film" in more and "First Film" not in more


def test_review_detail_without_related_reviews_has_no_empty_section(client, db_session, authenticated_client, test_user_data):
    user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
    only = crud.create_movie(db_session, user.id, MovieCreate(title="Only Film", director="A", year=2024,
                                                             review=LONG_REVIEW, review_public=True))
    db_session.commit()
    client.headers = {}
    html = client.get(f"/reviews/{only.id}?category=movie").text
    assert "review-more" not in html and "/static/poster-placeholder.svg" in html


def test_placeholder_artwork_is_served(client):
    response = client.get("/static/poster-placeholder.svg")
    assert response.status_code == 200 and "svg" in response.headers["content-type"]


INFO_PAGES = ["/about", "/faq", "/privacy", "/terms", "/contact", "/changelog", "/roadmap", "/site-map",
              "/content-quality", "/advertising"]


def test_info_pages_use_reader_layout_without_inline_styles(client):
    for path in INFO_PAGES:
        html = client.get(path).text
        assert '<body class="public-reader site">' in html, path
        assert "<style>" not in html.split("</head>")[0], path
        assert 'aria-label="Related pages"' not in html


def test_faq_answers_are_visible_without_javascript(client):
    css = client.get("/static/public-reader.css").text
    assert ".public-reader .faq-list .faq-answer { max-height: none;" in css
    assert "What is OmniTrackr?" in client.get("/faq").text


def test_browsers_get_a_styled_404_and_api_clients_keep_json(client):
    page = client.get("/definitely-missing", headers={"Accept": "text/html"})
    assert page.status_code == 404 and "This page drifted into the void" in page.text
    assert '<header class="site-header">' in page.text and "noindex" in page.text
    assert client.get("/definitely-missing").json() == {"detail": "Not Found"}
    assert client.get("/api/definitely-missing", headers={"Accept": "text/html"}).json() == {"detail": "Not Found"}
    assert client.post("/definitely-missing", headers={"Accept": "text/html"}).status_code in (404, 405)


def test_unavailable_pages_share_the_message_layout(client):
    missing_review = client.get("/reviews/999999?category=movie")
    assert missing_review.status_code == 404 and "site-message" in missing_review.text
    assert "Review not found" in missing_review.text
    missing_collection = client.get("/collections/public/999999/save")
    assert missing_collection.status_code == 404 and "This collection is unavailable" in missing_collection.text
    assert '<header class="site-header">' in missing_collection.text


def test_message_page_escapes_everything():
    html = site_chrome.message_page("<t>", "<h>", "<m>", eyebrow="<e>", actions=(('"x"', 'javascript:"'),))
    assert "<t>" not in html and "<h>" not in html and "<m>" not in html and "<e>" not in html
    assert '&quot;x&quot;' in html and 'href="javascript:&quot;"' in html
