"""Public pages load their fonts and images from OmniTrackr and keep their layout steady."""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
STATIC = APP / "static"
PUBLIC_PATHS = ["/", "/about", "/privacy", "/contact", "/advertising", "/guides", "/faq",
                "/media-tracking", "/movie-tracker", "/discover", "/terms"]


class TestSelfHostedFonts:
    def test_no_page_or_route_links_google_fonts(self):
        sources = list((APP / "templates").glob("*.html")) + list((APP / "routers").glob("*.py")) + [APP / "site_chrome.py"]
        offenders = [p.name for p in sources if re.search(r"fonts\.(googleapis|gstatic)\.com", p.read_text(encoding="utf-8"))]
        assert offenders == []

    def test_public_pages_use_local_fonts(self, client):
        for path in PUBLIC_PATHS:
            html = client.get(path).text
            assert "/static/fonts.css?v=" in html, path
            assert 'href="/static/fonts/poppins-800-latin.woff2" as="font" type="font/woff2" crossorigin' in html, path
            assert "fonts.googleapis.com" not in html, path

    def test_every_font_file_in_the_stylesheet_exists(self):
        css = (STATIC / "fonts.css").read_text(encoding="utf-8")
        files = re.findall(r"url\(/static/fonts/([\w.-]+\.woff2)\)", css)
        assert len(files) == 13
        for name in files:
            assert (STATIC / "fonts" / name).stat().st_size > 1000, name
        assert (STATIC / "fonts" / "OFL.txt").exists()

    def test_headings_never_swap_after_paint(self):
        css = (STATIC / "fonts.css").read_text(encoding="utf-8")
        for block in re.findall(r"@font-face \{(.*?)\}", css, re.S):
            display = re.search(r"font-display: (\w+)", block).group(1)
            assert display == ("optional" if "'Poppins'" in block else "swap")

    def test_font_files_are_cached_for_a_year(self, client):
        response = client.get("/static/fonts/inter-var-latin.woff2")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert client.get("/static/site.css").headers["cache-control"] == "public, max-age=86400"


class TestAssets:
    def test_media_tracking_screenshots_are_local_and_sized(self, client):
        html = client.get("/media-tracking").text
        assert "github.com/user-attachments" not in html
        images = re.findall(r'<img src="/static/tour/[^>]+>', html)
        assert len(images) == 4
        for tag in images:
            assert 'width="1280"' in tag and 'height="' in tag and 'loading="lazy"' in tag and "srcset=" in tag
            for src in re.findall(r"/static/tour/([\w-]+\.webp)", tag):
                assert (STATIC / "tour" / src).exists(), src

    def test_versioned_auth_script_is_cached_for_a_year(self, client):
        assert client.get("/auth.js?v=20261010-audit-goals-1").headers["cache-control"] == "public, max-age=31536000, immutable"
        assert client.get("/auth.js").headers["cache-control"] == "public, max-age=86400"

    def test_narrow_screens_keep_the_header_on_one_row(self):
        css = (STATIC / "site.css").read_text(encoding="utf-8")
        narrow = css[css.index("@media (max-width: 440px)"):]
        assert ".site-header .site-nav { flex-wrap: nowrap;" in narrow[:narrow.index("\n}")]
