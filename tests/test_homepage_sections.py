"""Guest homepage below the hero (Nov 15 2026): screen tour, live numbers, importing, free tools, sign-up rows."""
import os
import re
from datetime import datetime, timedelta

import pytest

from app import funnel, landing_proof, landing_sections, main, models
from app.binge_guides import GUIDES as BINGE_GUIDES
from app.in_order_guides import GUIDES as ORDER_GUIDES
from app.switch_guides import GUIDES as SWITCH_GUIDES

ROOT = os.path.dirname(os.path.dirname(__file__))
HOME_EVENTS = {"home_cta_clicked", "home_tour_opened", "home_import_clicked", "home_binge_demo_used", "home_tool_opened"}


# ---------------------------------------------------------------- screen tour

def test_tour_has_six_tabs_with_one_panel_showing(client):
    html = client.get("/").text
    section = html[html.index('id="how-it-works"'):]
    section = section[:section.index("</section>")]
    tabs = re.findall(r'<button type="button" role="tab"[^>]*>', section)
    assert len(tabs) == 6
    assert sum('aria-selected="true"' in tab for tab in tabs) == 1
    panels = re.findall(r'<div class="lp-shot" role="tabpanel"[^>]*>', section)
    assert len(panels) == 6 and sum(" hidden" in panel for panel in panels) == 5
    for tab in tabs:
        controls = re.search(r'aria-controls="([^"]+)"', tab).group(1)
        assert f'id="{controls}"' in section


def test_tour_images_exist_are_sized_and_described(client):
    html = client.get("/").text
    section = html[html.index('id="how-it-works"'):]
    section = section[:section.index("</section>")]
    images = re.findall(r"<img [^>]*>", section)
    assert len(images) == 12  # a browser and a phone screen per tab
    for tag in images:
        assert 'loading="lazy"' in tag and 'width="' in tag and 'height="' in tag
        alt = re.search(r'alt="([^"]*)"', tag).group(1)
        assert len(alt) > 20
        for src in re.findall(r"/static/tour/[a-z0-9-]+\.webp", tag):
            path = os.path.join(ROOT, "app", src.lstrip("/"))
            assert os.path.exists(path), src
            assert os.path.getsize(path) < 160_000, src  # keep the homepage light


# ---------------------------------------------------------------- live numbers

def test_pulse_needs_two_numbers_and_rounds_down():
    assert landing_proof.pulse_html({"members": 40, "titles": 90, "added": 10, "finished": 5}) == ""
    assert landing_proof.pulse_html({"members": 230, "titles": 40, "added": 3, "finished": 1}) == ""
    html = landing_proof.pulse_html({"members": 231, "titles": 6420, "added": 512, "finished": 80})
    assert "<strong class=\"lp-pulse__num\">200+</strong>" in html
    assert ">6,000+<" in html and ">500+<" in html and ">80<" in html
    assert "lp-pulse__list--4" in html
    three = landing_proof.pulse_html({"members": 231, "titles": 6420, "added": 512, "finished": 3})
    assert "lp-pulse__list--3" in three and "finished" not in three


def _member(db, name):
    user = models.User(username=name, email=f"{name}@example.com", hashed_password="x", is_active=True, is_verified=True)
    db.add(user)
    db.flush()
    return user


def test_pulse_counts_only_the_last_30_days(db_session):
    now = datetime(2026, 11, 15, 12, 0)
    user = _member(db_session, "pulse")
    db_session.add_all([
        models.Movie(user_id=user.id, title="New", added_at=now - timedelta(days=2)),
        models.Book(user_id=user.id, title="Also new", added_at=now - timedelta(days=29)),
        models.Movie(user_id=user.id, title="Old", added_at=now - timedelta(days=45)),
        models.ActivityEntry(user_id=user.id, category="movies", title="New", action="completed", occurred_at=now - timedelta(days=1)),
        models.ActivityEntry(user_id=user.id, category="movies", title="Re", action="revisited", occurred_at=now - timedelta(days=3)),
        models.ActivityEntry(user_id=user.id, category="movies", title="Old", action="completed", occurred_at=now - timedelta(days=40)),
        models.ActivityEntry(user_id=user.id, category="movies", title="New", action="started", occurred_at=now - timedelta(days=1)),
    ])
    db_session.flush()
    counts = landing_proof.pulse_counts(db_session, now=now)
    assert counts["added"] == 2 and counts["finished"] == 2
    assert counts["titles"] == 3 and counts["members"] == 1


def test_homepage_shows_the_pulse_band(client, monkeypatch):
    monkeypatch.setattr(landing_proof, "pulse_section",
                        lambda *a, **k: landing_proof.pulse_html({"members": 230, "titles": 6400, "added": 500, "finished": 90}))
    html = client.get("/").text
    assert "OmniTrackr right now" in html and "<!--HOME_PULSE-->" not in html
    assert html.index('id="how-it-works"') < html.index("lp-pulse") < html.index('id="import"')


# ---------------------------------------------------------------- importing

def test_import_section_lists_every_service_with_a_guide(client):
    html = landing_sections.import_section()
    hrefs = re.findall(r'href="(/switch/[^"]+)"', html)
    assert len(hrefs) == 13
    assert {h.rsplit("/", 1)[1] for h in hrefs} == set(SWITCH_GUIDES)
    assert "from 13 apps and sites" in html
    for href in set(hrefs):
        assert client.get(href).status_code == 200, href
    assert 'href="/?start=import#signup"' in html and "data-home-import" in html


# ---------------------------------------------------------------- free tools

def test_binge_demo_matches_the_guides():
    from app import binge_calculator
    html = landing_sections.binge_demo_html()
    options = re.findall(r'<option value="([^"]+)" data-minutes="(\d+)" data-episodes="(\d+)"', html)
    assert [slug for slug, _, _ in options] == [s for s in landing_sections.BINGE_DEMO if s in BINGE_GUIDES]
    slug, minutes, episodes = options[0]
    totals = binge_calculator.totals(BINGE_GUIDES[slug])
    assert int(minutes) == round(totals["minutes"]) and int(episodes) == totals["episodes"]
    days = binge_calculator.days_at(totals["minutes"], landing_sections.BINGE_DEFAULT_PACE)
    assert f"<strong data-binge-days>{days}</strong>" in html
    assert f'href="/binge-calculator/{slug}"' in html
    assert html.count('aria-pressed="true"') == 1


def test_tools_section_links_work(client):
    html = landing_sections.tools_section()
    assert f"{len(ORDER_GUIDES)} series" in html
    assert f"has {len(BINGE_GUIDES)} hand-checked guides" in html
    for href in sorted(set(re.findall(r'href="(/[^"#]*)"', html))):
        assert client.get(href, follow_redirects=False).status_code in (200, 301, 302, 307, 308), href


def test_homepage_survives_broken_sections(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("section exploded")

    monkeypatch.setattr(landing_sections, "tools_section", boom)
    monkeypatch.setattr(landing_sections, "import_section", boom)
    monkeypatch.setattr(landing_proof, "pulse_section", boom)
    response = client.get("/")
    assert response.status_code == 200
    assert "HOME_TOOLS" not in response.text and "HOME_IMPORT" not in response.text and "HOME_PULSE" not in response.text
    assert "section exploded" not in response.text


# ---------------------------------------------------------------- sign-up rows and counters

def test_sign_up_rows_with_and_without_google():
    plain = main.home_cta_html(False, "tour")
    assert "/auth/google/start" not in plain and 'data-action="show-register-form" data-home-cta="tour"' in plain
    google = main.home_cta_html(True, "tools")
    assert 'data-google-signup data-home-cta="tools"' in google and "Sign up with email" in google


def test_homepage_has_two_sign_up_rows(client):
    html = client.get("/").text
    assert html.count('class="lp-cta lp-cta--') == 2
    assert "HOME_CTA" not in html


def test_new_events_are_counted_and_labelled():
    assert HOME_EVENTS <= funnel.CLIENT_EVENTS and HOME_EVENTS <= funnel.SERVER_EVENTS
    labelled = {name for name, _ in funnel.GUEST}
    assert HOME_EVENTS <= labelled


def test_landing_script_reports_the_new_events():
    script = open(os.path.join(ROOT, "app", "static", "public-landing.js"), encoding="utf-8").read()
    for event in HOME_EVENTS:
        assert f"report('{event}')" in script, event
    # The import button keeps the same intent key auth.js reads for /?start=import.
    assert "'omnitrackr_demo_start'" in script
    assert "DEMO_START_KEY = 'omnitrackr_demo_start'" in open(os.path.join(ROOT, "app", "static", "auth.js"), encoding="utf-8").read()


@pytest.mark.parametrize("path", ["app/static/public-landing.css"])
def test_new_sections_have_phone_rules(path):
    css = open(os.path.join(ROOT, path), encoding="utf-8").read()
    phone = css[css.rindex("@media (max-width: 680px)"):]
    assert ".lp-shot__browser { display: none; }" in phone
