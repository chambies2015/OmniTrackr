"""Oct 27, 2026 AdSense pass: monthly editions go live on their own date, and the
November edition pairs with the November challenge."""
from datetime import date

from app import challenges, pick
from app.discover_catalog import MONTHLY_EDITIONS, published_editions

NOVEMBER = MONTHLY_EDITIONS["november-2026"]


def test_editions_publish_on_their_date():
    assert "november-2026" not in published_editions(date(2026, 10, 31))
    assert "november-2026" in published_editions(date(2026, 11, 1))
    assert list(published_editions(date(2026, 11, 1))) == list(MONTHLY_EDITIONS)


def test_an_edition_before_its_date_has_no_page_or_links(client, monkeypatch):
    monkeypatch.setitem(NOVEMBER, "published_date", "2999-01-01")
    assert client.get("/discover/monthly/november-2026").status_code == 404
    assert "november-2026" not in client.get("/sitemap.xml").text
    assert NOVEMBER["name"] not in client.get("/discover").text
    assert "november-2026" not in client.get("/").text
    assert all("november-2026" not in (entry["source_url"] or "") for entry in pick.pool())


def test_an_edition_on_its_date_is_live_everywhere(client, monkeypatch):
    monkeypatch.setitem(NOVEMBER, "published_date", "2026-10-01")
    page = client.get("/discover/monthly/november-2026")
    assert page.status_code == 200
    assert "noindex" not in page.headers.get("x-robots-tag", "")
    assert NOVEMBER["essay_title"] in page.text
    assert "/discover/monthly/november-2026" in client.get("/sitemap.xml").text
    assert "/discover/monthly/november-2026" in client.get("/discover").text
    assert any((entry["source_url"] or "").endswith("/november-2026") for entry in pick.pool())


def test_november_challenge_links_its_edition_once_live(client, monkeypatch):
    monkeypatch.setattr(challenges, "public_months", lambda today=None: ["2026-11", "2026-10"])
    monkeypatch.setitem(NOVEMBER, "published_date", "2999-01-01")
    assert "/discover/monthly/november-2026" not in client.get("/challenges/november-2026").text
    monkeypatch.setitem(NOVEMBER, "published_date", "2026-10-01")
    page = client.get("/challenges/november-2026").text
    assert "Reading for the month" in page and "/discover/monthly/november-2026" in page
    # October's edition is a challenge step, so it isn't repeated as a companion.
    assert "Reading for the month" not in client.get("/challenges/october-2026").text


def test_november_picks_fit_the_month():
    # The November challenge asks for something from before 2000 and a book.
    years = [item["meta"].get("year") for item in NOVEMBER["items"] if item["meta"].get("year")]
    assert years and all(year < 2000 for year in years)
    assert any(item["category"] == "books" for item in NOVEMBER["items"])
