"""November 25 2026 pass before the AdSense resubmit: thin member charts, guide sections, trust pages."""
from datetime import datetime, timedelta

from app import corrections_log, models, title_charts, trending
from app.binge_guides import GUIDES as BINGE
from tests.test_title_pages import add_movie, member


def test_trending_chart_from_a_few_members_stays_out_of_search(client, db_session):
    # Enough titles to chart, but the same three people behind every one of them.
    now = datetime.utcnow()
    people = [member(db_session, f"few{index}") for index in range(3)]
    for number in range(trending.INDEX_MIN_OVERALL):
        for user in people:
            item = models.Movie(user_id=user.id, title=f"Few Film {number}", year=2000 + number,
                                added_at=now - timedelta(days=1))
            db_session.add(item)
            db_session.flush()
            db_session.add(models.ActivityEntry(user_id=user.id, category="movies", item_id=item.id,
                                                title=item.title, action="completed",
                                                occurred_at=now - timedelta(hours=5)))
    db_session.commit()
    trending.clear_cache()
    response = client.get("/trending/movie")
    assert response.status_code == 200 and "Few Film" in response.text  # The chart still shows.
    assert response.headers["X-Robots-Tag"] == "noindex, follow"
    sitemap = client.get("/sitemap.xml").text
    assert "/trending</loc>" not in sitemap and "/trending/movie</loc>" not in sitemap


def test_member_chart_rated_by_a_few_people_stays_out_of_search(client, db_session):
    people = [member(db_session, f"rater{index}") for index in range(3)]
    for number in range(title_charts.CHART_INDEX_MIN):
        for user, rating in zip(people, (7, 8, 9)):
            add_movie(db_session, user, title=f"Rated Film {number}", year=2000 + number, rating=rating, watched=True)
    db_session.commit()
    title_charts.clear_cache()
    data = title_charts.build(db_session, "movie")
    assert len(data["ranked"]) == title_charts.CHART_INDEX_MIN and not data["indexable"]
    assert all("_raters" not in entry for entry in data["ranked"] + data["tracked"])
    response = client.get("/titles/movie")
    assert response.status_code == 200 and "Rated Film" in response.text
    assert response.headers["X-Robots-Tag"] == "noindex, follow"
    assert "/titles/movie</loc>" not in client.get("/sitemap.xml").text


def test_new_binge_sections_are_on_their_pages_and_in_the_log(client):
    change = next(change for change in corrections_log.guide_changes() if change.date == "2026-11-25"
                  and change.kind == "added")
    logged = dict(change.pages)
    assert len(logged) == 10
    for slug, ids in corrections_log._NOV25_ADDED.items():
        guide = BINGE[slug]
        assert guide["reviewed"] == "2026-11-25", slug
        assert [section[0] for section in guide["sections"]][-len(ids):] == list(ids), slug
        html = client.get(f"/binge-calculator/{slug}").text
        for section_id, heading, _ in guide["sections"]:
            if section_id in ids:
                assert heading in html and heading in logged[f"/binge-calculator/{slug}"], slug
    # The older entries still name only the guides they were about.
    older = {change.date: dict(change.pages) for change in corrections_log.guide_changes()
             if "How long it takes" in change.label}
    assert len(older["2026-11-20"]) == 28 and len(older["2026-11-23"]) == 9
    assert "/binge-calculator/one-piece" not in older["2026-11-20"]
    assert "/binge-calculator/breaking-bad" not in older["2026-11-23"]
    assert "1180" in logged["/binge-calculator/one-piece"] and "2027" in BINGE["one-piece"]["faq"][0][1]


def test_seasonal_hubs_say_six_formats(client):
    for path in ("/halloween", "/holidays"):
        html = client.get(path).text
        assert "one pick in every format OmniTrackr tracks:" not in html, path
        assert "one pick in each of six formats: a film" in html, path
        assert "It was written in October, before manga, podcasts and audiobooks joined" in html, path


def test_watch_together_answers_common_questions(client):
    html = client.get("/together").text
    assert "Questions people ask" in html and "Do my friends need an account?" in html
    assert "eight weeks after its last week" in html


def test_about_lists_the_seasonal_guides_and_friend_tools(client):
    html = client.get("/about").text
    for href in ("/valentines-day", "/awards", "/break", "/together", "/swap", "/holidays/thanksgiving"):
        assert f'href="{href}"' in html, href
    assert "does the same for the winter break" not in html
    quality = client.get("/content-quality").text
    assert "advent calendar opens one door a day" in quality
    assert "from January 2027 each edition has nine" in quality
