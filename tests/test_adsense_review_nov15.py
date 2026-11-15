"""November 15, 2026 pass before the next AdSense review request."""
import re

from app import binge_calculator, editorial_index, guide_links
from app.binge_guides import GUIDES as BINGE_GUIDES
from app.html_finish import finish
from app.link_hints import nofollow_account_links


def test_binge_guides_are_in_the_editorial_index():
    hrefs = {piece["href"]: piece for piece in editorial_index.entries()}
    indexable = [slug for slug, guide in BINGE_GUIDES.items() if binge_calculator.is_indexable(guide)]
    assert indexable
    for slug in indexable:
        piece = hrefs[binge_calculator.path(slug)]
        assert piece["section"] == "binge"
        assert piece["name"].startswith("How long")
        assert piece["updated"] == BINGE_GUIDES[slug]["reviewed"]


def test_short_binge_guides_stay_out_of_the_index(monkeypatch):
    slug = next(iter(BINGE_GUIDES))
    monkeypatch.setattr(binge_calculator, "is_indexable", lambda guide: guide is not BINGE_GUIDES[slug])
    hrefs = {piece["href"] for piece in editorial_index.entries()}
    assert binge_calculator.path(slug) not in hrefs


def test_ledger_lists_the_binge_guides(client):
    html = client.get("/content-quality").text
    ledger = html[html.index('id="ledger-heading"'):]
    assert 'href="/binge-calculator">How long it takes</a>' in ledger
    assert 'href="/binge-calculator/breaking-bad"' in ledger
    assert "<h3>How long it takes</h3>" in html and "<h3>Awards season</h3>" in html


def test_binge_and_franchise_guides_link_to_each_other():
    guide_links._index_for.cache_clear()
    related = {link["href"] for link in guide_links.related("/binge-calculator/game-of-thrones")}
    assert "/in-order/game-of-thrones" in related
    back = {link["href"] for link in guide_links.related("/in-order/game-of-thrones")}
    assert "/binge-calculator/game-of-thrones" in back


def test_account_links_get_nofollow():
    html = ('<a class="button" href="/?next=%2Fholidays%2Fgifts#signup">Start</a>'
            '<a href="/?next=/release-radar" rel="noopener">In</a>'
            '<a rel="nofollow" href="/?login=1">Log in</a>'
            '<a href="https://omnitrackr.xyz/?next=%2Ftonight">Abs</a>'
            '<a href="/about">About</a><a href="/in-order?next=x">Other page</a>')
    out = nofollow_account_links(html)
    assert out.count("nofollow") == 4
    assert 'rel="noopener nofollow"' in out
    assert '<a href="/about">' in out and '<a href="/in-order?next=x">' in out
    assert nofollow_account_links(out) == out


def test_finish_runs_the_nofollow_step():
    assert 'rel="nofollow"' in finish('<html><body><a href="/?next=%2Fx#signup">Join</a></body></html>')


def test_public_pages_have_no_followed_account_links(client):
    for path in ("/holidays/gifts", "/holidays/black-friday", "/release-radar", "/tonight",
                 "/discover/one-evening-well-spent", "/awards/oscars-2027"):
        html = client.get(path).text
        for tag in re.findall(r'<a\b[^>]*href="/\?(?:next|login)=[^"]*"[^>]*>', html):
            assert "nofollow" in tag, (path, tag)


def test_privacy_policy_covers_the_november_features(client):
    html = client.get("/privacy").text
    for label in ("Two-step sign-in (optional):", "Passkeys (optional):", "Episode notes:", "Award ballots:",
                  "Advent calendar:", "Gift lists:", "Shared lists and clubs:", "Things saved before you sign up:",
                  "Ko-fi:", "Amazon Associates:"):
        assert f"<strong>{label}</strong>" in html, label
    assert "As an Amazon Associate, OmniTrackr earns from qualifying purchases" in html
    assert "Last Updated: November 15, 2026" in html


def test_calculator_lookup_links_from_title_pages_are_nofollow():
    from types import SimpleNamespace
    from app.routers.titles import _binge_link
    html = _binge_link(SimpleNamespace(kind="tv", title="An Unlisted Show", year=2020))
    assert "/binge-calculator?lookup=tv" in html and 'rel="nofollow"' in html
