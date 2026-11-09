"""Sweep of the Nov 9 merges: the Black Friday guide (#187), Next Up's Start, drag and
suggestions (#188), the Nov 8 sweep (#189) and the title page redesign (#190)."""
import copy
import re
from contextlib import contextmanager
from datetime import date

from sqlalchemy import event

from app import models
from app.routers import deals_guide
from tests.conftest import engine
from tests.test_title_detail_redesign import WHERE, page


@contextmanager
def counted_queries():
    seen = []

    def count(*args, **kwargs):
        seen.append(1)

    event.listen(engine, "before_cursor_execute", count)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", count)


def _long_queue(authenticated_client, db_session, size=30):
    user = db_session.query(models.User).filter(models.User.username == "testuser").one()
    for position in range(size):
        movie = models.Movie(user_id=user.id, title=f"Queued film {position}", year=1950 + position, watched=False)
        db_session.add(movie)
        db_session.flush()
        db_session.add(models.NextUpItem(user_id=user.id, category="movies", item_id=movie.id, position=position))
    db_session.commit()
    return authenticated_client.get("/next-up/").json()


class TestQueueWritesDontReloadEveryRow:
    """Start, drag reorder and Clear finished committed and then serialised the queue rows
    they already held. The commit expires them, so each row was read back with its own
    query: about 60 queries to start one title in a 45-title queue."""

    def test_starting_a_title_reads_the_queue_once(self, authenticated_client, db_session):
        queue = _long_queue(authenticated_client, db_session)
        target = queue[20]
        with counted_queries() as seen:
            response = authenticated_client.post(f"/next-up/{target['id']}/start")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body[0]["id"] == target["id"] and body[0]["started_at"]
        assert [item["title"] for item in body[1:]] == [item["title"] for item in queue if item["id"] != target["id"]]
        assert len(seen) < 25

    def test_dragging_a_title_reads_the_queue_once(self, authenticated_client, db_session):
        queue = _long_queue(authenticated_client, db_session)
        target = queue[0]
        with counted_queries() as seen:
            response = authenticated_client.put(f"/next-up/{target['id']}/position", json={"position": 29})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body[-1]["id"] == target["id"]
        assert [item["position"] for item in body] == list(range(30))
        assert len(seen) < 25

    def test_clear_finished_reads_the_queue_once(self, authenticated_client, db_session):
        queue = _long_queue(authenticated_client, db_session)
        finished = db_session.get(models.Movie, queue[3]["item_id"])
        finished.watched = True
        db_session.commit()
        with counted_queries() as seen:
            response = authenticated_client.post("/next-up/clear-finished")
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body) == 29 and queue[3]["id"] not in {item["id"] for item in body}
        assert [item["position"] for item in body] == list(range(29))
        assert len(seen) < 25

    def test_another_members_queue_entry_still_cant_be_started(self, authenticated_client, client, db_session):
        queue = _long_queue(authenticated_client, db_session, size=2)
        other = models.User(username="other_queue", email="other_queue@example.test", hashed_password="unused",
                            is_active=True, is_verified=True)
        db_session.add(other)
        db_session.commit()
        from app import auth
        client.headers["Authorization"] = "Bearer " + auth.create_access_token({"sub": other.username})
        assert client.post(f"/next-up/{queue[1]['id']}/start").status_code == 404
        assert client.delete(f"/next-up/{queue[1]['id']}/start").status_code == 404
        assert client.get("/next-up/suggestions").json() == []


class TestTitleHero:
    def test_more_services_counts_each_service_once(self, client, db_session):
        where = copy.deepcopy(WHERE)
        # Apple TV and YouTube to rent and to buy are still two more places, not four.
        where["groups"].append({"label": "Buy", "providers": [{"name": "Apple TV"}, {"name": "YouTube"}]})
        html = page(client, db_session, where=where)
        teaser = html.split('class="title-hero__where"', 1)[1].split("</a>", 1)[0]
        assert "+2 more" in teaser

    def test_no_more_label_when_the_rest_repeat_the_first_row(self, client, db_session):
        where = copy.deepcopy(WHERE)
        where["groups"][1]["providers"] = [{"name": "Netflix"}]
        html = page(client, db_session, where=where)
        teaser = html.split('class="title-hero__where"', 1)[1].split("</a>", 1)[0]
        assert "more</span>" not in teaser

    def test_the_wide_still_is_fetched_early(self, client, db_session):
        html = page(client, db_session)
        backdrop = re.search(r'<img class="title-hero__backdrop"[^>]*>', html).group(0)
        assert "w1280/wide.jpg" in backdrop and 'fetchpriority="high"' in backdrop

    def test_trailer_button_name_includes_its_visible_text(self, client, db_session):
        html = page(client, db_session)
        button = re.search(r'<button type="button" class="title-trailer"[^>]*>', html).group(0)
        label = re.search(r'aria-label="([^"]*)"', button).group(1)
        assert "Plays from YouTube (privacy-enhanced mode)" in label and "Interstellar" in label


def test_black_friday_guide_names_the_year_its_dates_are_for():
    """The hero printed today's year, so in January the 2026 calendar would be headed 2027."""
    html = deals_guide.guide_content(pages={}, signed_in=False, today=date(2027, 1, 5))
    assert "BLACK FRIDAY AND CYBER MONDAY 2026" in html
    assert "CYBER MONDAY 2027" not in html
