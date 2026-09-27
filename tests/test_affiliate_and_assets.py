"""Affiliate links stay off until configured; optimized vortex assets keep the original look."""
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from app import affiliate, crud, models
from app import release_radar as radar
from app.schemas import MovieCreate
from tests.release_radar_fixtures import install_fixture_providers
from datetime import date

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
LONG_REVIEW = (
    "The film builds its tension slowly, trusting quiet scenes and a patient score before the final act. "
    "Its lead performance carries the uncertainty well, and the second half rewards anyone who stays with it. "
    "I would recommend it to viewers who like character studies more than twists, and would watch it again."
)


class TestAffiliateLinks:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv("AMAZON_ASSOCIATES_TAG", raising=False)
        assert affiliate.links_for("movies", "Digger") == []
        assert affiliate.links_html("books", "Earthsea") == ""
        assert affiliate.disclosure_html() == ""

    def test_invalid_tags_are_ignored(self, monkeypatch):
        for bad in ("", "a", "tag with spaces", 'x"><script>', "x" * 41):
            monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", bad)
            assert affiliate.links_for("games", "Anything") == []

    def test_links_carry_tag_and_category(self, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", "omnitrackr-20")
        [link] = affiliate.links_for("video_game", "Fixture: Starfall Odyssey")
        url = urlsplit(link["url"])
        query = parse_qs(url.query)
        assert url.scheme == "https" and url.netloc == "www.amazon.com" and url.path == "/s"
        assert query == {"k": ["Fixture: Starfall Odyssey"], "i": ["videogames"], "tag": ["omnitrackr-20"]}
        [book] = affiliate.links_for("book", "A Wizard of Earthsea", "Ursula K. Le Guin")
        assert parse_qs(urlsplit(book["url"]).query)["k"] == ["A Wizard of Earthsea Ursula K. Le Guin"]
        assert affiliate.links_for("podcast", "X") == [] and affiliate.links_for("movies", "  ") == []

    def test_html_is_escaped_and_marked_sponsored(self, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", "omnitrackr-20")
        html = affiliate.links_html("movies", '"><img src=x onerror=alert(1)>')
        assert "<img" not in html
        assert 'rel="sponsored noopener noreferrer"' in html and 'target="_blank"' in html
        assert "Amazon Associate" in affiliate.disclosure_html()

    def test_radar_cards_show_links_only_when_enabled(self, client, monkeypatch):
        install_fixture_providers(today=date(2026, 9, 27), monkeypatch=monkeypatch)
        monkeypatch.delenv("AMAZON_ASSOCIATES_TAG", raising=False)
        off = client.get("/release-radar/games").text
        assert "amazon.com" not in off and "Amazon Associate" not in off
        monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", "omnitrackr-20")
        on = client.get("/release-radar/games").text
        assert on.count("tag=omnitrackr-20") >= 5
        assert "As an Amazon Associate OmniTrackr earns from qualifying purchases" in on

    def test_review_detail_link_is_optional(self, client, db_session, authenticated_client, test_user_data, monkeypatch):
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        movie = crud.create_movie(db_session, user.id, MovieCreate(
            title="Affiliate Test Movie", director="A Director", year=2025, review=LONG_REVIEW, review_public=True))
        db_session.commit()
        client.headers = {}
        monkeypatch.delenv("AMAZON_ASSOCIATES_TAG", raising=False)
        page = client.get(f"/reviews/{movie.id}?category=movie")
        assert page.status_code == 200 and "amazon.com" not in page.text
        monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", "omnitrackr-20")
        page = client.get(f"/reviews/{movie.id}?category=movie")
        assert "tag=omnitrackr-20" in page.text and "Affiliate+Test+Movie" in page.text
        assert "Amazon Associate" in page.text

    def test_discover_trails_stay_affiliate_free(self, client, monkeypatch):
        monkeypatch.setenv("AMAZON_ASSOCIATES_TAG", "omnitrackr-20")
        assert "amazon.com" not in client.get("/discover/finding-your-feet").text

    def test_advertising_policy_discloses_affiliates(self, client):
        text = client.get("/advertising").text
        assert "Affiliate Links" in text and "Amazon Associate" in text


class TestVortexAssets:
    def test_webp_renditions_are_small_and_served(self, client):
        for path, limit in (("/vortex.webp", 600_000), ("/vortex-still.webp", 60_000), ("/omnitrackr_vortex.webp", 150_000)):
            response = client.get(path)
            assert response.status_code == 200, path
            assert response.headers["content-type"] == "image/webp"
            assert "max-age" in response.headers["cache-control"]
            assert response.content[:4] == b"RIFF" and response.content[8:12] == b"WEBP"
            assert len(response.content) < limit
            assert client.head(path).status_code == 200
        # Originals stay available for social previews and older caches.
        assert client.get("/vortex.gif").status_code == 200
        assert client.get("/omnitrackr_vortex.png").status_code == 200

    def test_animated_webp_keeps_every_frame_and_loops(self):
        data = (STATIC / "vortex.webp").read_bytes()
        assert b"ANIM" in data and data.count(b"ANMF") == 91
        loop_offset = data.index(b"ANIM") + 8 + 4
        assert int.from_bytes(data[loop_offset:loop_offset + 2], "little") == 0  # loop forever

    def test_css_prefers_webp_with_gif_fallback_and_respects_reduced_motion(self):
        css = (STATIC / "styles.css").read_text(encoding="utf-8")
        assert "url('/vortex.gif');\n  background-image: image-set(url('/vortex.webp') type('image/webp'), url('/vortex.gif') type('image/gif'));" in css
        assert re.search(r"image-set\(url\('/omnitrackr_vortex\.webp'\) type\('image/webp'\), url\('/omnitrackr_vortex\.png'\)", css)
        reduced = css[css.index("@media (prefers-reduced-motion: reduce) {\n  .landing-hero"):]
        assert "/vortex-still.webp" in reduced[:400]
