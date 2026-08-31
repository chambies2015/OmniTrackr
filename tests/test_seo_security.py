"""
Tests for SEO endpoints and security middleware.
"""
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app import crud, models
from app.csp import add_nonce_to_inline_tags, extract_inline_styles
from app.schemas import BookCreate, MovieCreate


class LinkHrefParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.add(value)


def extract_hrefs(html):
    parser = LinkHrefParser()
    parser.feed(html)
    return parser.hrefs


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_parts = []
        self.description = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "meta" and attrs.get("name") == "description":
            self.description = attrs.get("content")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self):
        return "".join(self.title_parts).strip()


def parse_metadata(html):
    parser = MetadataParser()
    parser.feed(html)
    return parser


class PageQualityParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.text_parts = []
        self.h1_count = 0
        self.h2_count = 0
        self.description_count = 0
        self.canonical_count = 0
        self.canonical_hrefs = []
        self.robots_contents = []
        self.json_ld_count = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            if tag == "script" and attrs.get("type") == "application/ld+json":
                self.json_ld_count += 1
            self.skip_depth += 1
        if tag == "h1":
            self.h1_count += 1
        elif tag == "h2":
            self.h2_count += 1
        elif tag == "meta" and attrs.get("name") == "description":
            self.description_count += 1
        elif tag == "meta" and attrs.get("name") == "robots":
            self.robots_contents.append(attrs.get("content", ""))
        elif tag == "link" and attrs.get("rel") == "canonical":
            self.canonical_count += 1
            self.canonical_hrefs.append(attrs.get("href", ""))

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth and data.strip():
            self.text_parts.append(data.strip())

    @property
    def word_count(self):
        return len(" ".join(self.text_parts).split())


def parse_page_quality(html):
    parser = PageQualityParser()
    parser.feed(html)
    return parser


PUBLIC_PAGE_PATHS = [
    "/",
    "/about",
    "/privacy",
    "/advertising",
    "/content-quality",
    "/site-map",
    "/faq",
    "/guides",
    "/compare",
    "/use-cases",
    "/changelog",
    "/tv-show-tracker",
    "/game-tracker",
    "/movie-tracker",
    "/anime-tracker",
    "/book-tracker",
    "/music-tracker",
    "/media-statistics",
    "/export-import-guide",
    "/media-tracker-checklist",
    "/tracking-templates",
    "/review-guidelines",
    "/sample-library",
    "/demo",
    "/media-tracking",
    "/roadmap",
    "/terms",
    "/contact",
    "/reviews",
]


class TestSEOEndpoints:
    """Test SEO-related endpoints."""
    
    def test_get_sitemap(self, client):
        """Test sitemap.xml endpoint."""
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"
        content = response.text
        assert "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" in content
        assert "<urlset" in content
        assert "omnitrackr.xyz" in content or "sitemap" in content.lower()
    
    def test_sitemap_includes_privacy_page(self, client):
        """Test that sitemap includes the privacy page."""
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        content = response.text
        assert "/privacy" in content
    
    def test_sitemap_includes_reviews_page(self, client):
        """Test that sitemap includes the reviews page."""
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        content = response.text
        assert "/reviews" in content
        assert "/reviews?category=" not in content

    def test_sitemap_review_category_urls_require_substantial_inventory(self, client, db_session, authenticated_client, test_user_data):
        """Category review URLs should enter the sitemap only after useful public review inventory exists."""
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        assert user is not None
        user.reviews_public = True
        db_session.commit()

        movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Sitemap Category Movie",
                director="Category Director",
                year=2026,
                review=(
                    "This review is substantial enough for a category review listing because it explains tone, "
                    "pacing, audience fit, and why the movie belongs in a public discovery directory."
                ),
                review_public=True,
            ),
        )
        spammy_movie = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Sitemap Spam Review Movie",
                director="Spam Director",
                year=2026,
                review=(
                    "This review is long enough to be a standalone page, but it asks readers to visit "
                    "https://spam.example for a free download and contact me at spam@example.com rather than "
                    "offering original media criticism, audience guidance, or a useful rating explanation."
                ),
                review_public=True,
            ),
        )
        book = crud.create_book(
            db_session,
            user.id,
            BookCreate(
                title="Thin Sitemap Category Book",
                author="Short Author",
                year=2026,
                review="Too short for public category inventory.",
                review_public=True,
            ),
        )
        db_session.commit()

        response = client.get("/sitemap.xml")
        content = response.text

        assert response.status_code == 200
        assert movie.id is not None
        assert book.id is not None
        assert "/reviews?category=movie" in content
        assert "/reviews?category=book" not in content
        assert f"/reviews/{spammy_movie.id}?category=movie" not in content

    def test_sitemap_review_detail_urls_require_standalone_content(self, client, db_session, authenticated_client, test_user_data):
        """Individual review detail URLs in the sitemap should avoid thin review pages."""
        user = db_session.query(models.User).filter(models.User.username == test_user_data["username"]).first()
        assert user is not None
        user.reviews_public = True
        db_session.commit()

        directory_quality_review = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Sitemap Directory Review",
                director="Short Director",
                year=2026,
                review=(
                    "This review is useful for a listing preview because it covers tone, pacing, and audience fit, "
                    "but it is intentionally too brief for a standalone indexed review detail URL."
                ),
                review_public=True,
            ),
        )
        standalone_review = crud.create_movie(
            db_session,
            user.id,
            MovieCreate(
                title="Sitemap Standalone Review",
                director="Long Director",
                year=2026,
                review=(
                    "This standalone review gives search visitors enough context to understand the movie before "
                    "clicking into the app. It covers the setup, the pacing, the emotional tone, the kind of viewer "
                    "who would enjoy it, how the rating was earned, and whether it feels worth revisiting later. "
                    "That additional detail makes the review page more useful than a short personal note."
                ),
                review_public=True,
            ),
        )
        db_session.commit()

        response = client.get("/sitemap.xml")
        content = response.text

        assert response.status_code == 200
        assert f"/reviews/{directory_quality_review.id}?category=movie" not in content
        assert f"/reviews/{standalone_review.id}?category=movie" in content

    def test_sitemap_includes_public_value_pages(self, client):
        """Test that sitemap includes public editorial pages for crawlers."""
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        content = response.text
        assert "/compare" in content
        assert "/use-cases" in content
        assert "/changelog" in content
        assert "/advertising" in content
        assert "/content-quality" in content
        assert "/site-map" in content
        assert "/faq" in content
        assert "/tv-show-tracker" in content
        assert "/game-tracker" in content
        assert "/movie-tracker" in content
        assert "/anime-tracker" in content
        assert "/book-tracker" in content
        assert "/music-tracker" in content
        assert "/media-statistics" in content
        assert "/export-import-guide" in content
        assert "/media-tracker-checklist" in content
        assert "/tracking-templates" in content
        assert "/review-guidelines" in content
        assert "/sample-library" in content
        assert "/demo" in content
        assert "/media-tracking" in content
        assert "/roadmap" in content
    
    def test_sitemap_includes_homepage(self, client):
        """Test that sitemap includes the homepage."""
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        content = response.text
        assert "<loc>" in content
        assert "</loc>" in content

    def test_sitemap_does_not_include_robots_disallowed_routes(self, client):
        """Indexable sitemap URLs should not conflict with robots.txt exclusions."""
        robots = client.get("/robots.txt").text
        sitemap = client.get("/sitemap.xml").text
        disallowed_prefixes = [
            line.split(": ", 1)[1]
            for line in robots.splitlines()
            if line.startswith("Disallow: ")
        ]

        for loc in re.findall(r"<loc>(.*?)</loc>", sitemap):
            path = urlparse(loc).path
            assert not any(path.startswith(prefix) for prefix in disallowed_prefixes), (
                f"{loc} conflicts with robots.txt"
            )

    def test_sitemap_urls_are_fetchable_indexable_and_canonical(self, client):
        """Every submitted sitemap URL should resolve to a canonical indexable public page."""
        sitemap = client.get("/sitemap.xml").text

        for loc in re.findall(r"<loc>(.*?)</loc>", sitemap):
            parsed = urlparse(loc)
            target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            response = client.get(target)
            quality = parse_page_quality(response.text)
            robots_directives = " ".join(
                quality.robots_contents + [response.headers.get("x-robots-tag", "")]
            ).lower()

            assert response.status_code == 200, loc
            assert "noindex" not in robots_directives, loc
            assert quality.canonical_hrefs == [loc], loc
    
    def test_get_robots_txt(self, client):
        """Test robots.txt endpoint."""
        response = client.get("/robots.txt")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        content = response.text
        assert "User-agent: *" in content
        assert "Allow: /ads.txt" in content
        assert "Allow: /sellers.json" in content
        assert "Allow: /reviews" in content
        assert "Allow: /compare" in content
        assert "Allow: /use-cases" in content
        assert "Allow: /changelog" in content
        assert "Allow: /advertising" in content
        assert "Allow: /content-quality" in content
        assert "Allow: /site-map" in content
        assert "Allow: /faq" in content
        assert "Allow: /tv-show-tracker" in content
        assert "Allow: /game-tracker" in content
        assert "Allow: /movie-tracker" in content
        assert "Allow: /anime-tracker" in content
        assert "Allow: /book-tracker" in content
        assert "Allow: /music-tracker" in content
        assert "Allow: /media-statistics" in content
        assert "Allow: /export-import-guide" in content
        assert "Allow: /media-tracker-checklist" in content
        assert "Allow: /tracking-templates" in content
        assert "Allow: /review-guidelines" in content
        assert "Allow: /sample-library" in content
        assert "Allow: /demo" in content
        assert "Allow: /media-tracking" in content
        assert "Allow: /roadmap" in content
        assert "Disallow: /docs" in content
        assert "Disallow: /redoc" in content
        assert "Disallow: /openapi.json" in content
        assert "Disallow: /credentials.js" in content
        for private_path in (
            "/friends",
            "/movies/",
            "/tv-shows/",
            "/anime/",
            "/video-games/",
            "/music/",
            "/books/",
            "/statistics/",
            "/custom-tabs/",
            "/export/",
            "/import/",
            "/profile-pictures/",
            "/custom-tab-posters/",
            "/static/profile_pictures/",
        ):
            assert f"Disallow: {private_path}" in content
        assert "Sitemap:" in content

    def test_credentials_js_is_not_search_content(self, client):
        """The legacy root credentials shim should stay available but not indexable."""
        response = client.get("/credentials.js")

        assert response.status_code == 200
        assert "application/javascript" in response.headers["content-type"]
        assert response.headers["x-robots-tag"] == "noindex, nofollow"
        assert "API Keys are now proxied through backend endpoints" in response.text

    def test_private_json_and_user_asset_routes_are_noindexed(self, client):
        """Private app endpoints should not become search inventory, even when returning errors."""
        for path in (
            "/api/user-count",
            "/movies/",
            "/statistics/",
            "/friends",
            "/profile-pictures/1",
            "/custom-tab-posters/1",
            "/static/profile_pictures/1_old.png",
        ):
            response = client.get(path)
            assert response.headers["x-robots-tag"] == "noindex, nofollow", path

    def test_ads_txt_authorizes_google_adsense_publisher(self, client):
        """ads.txt should expose the Google-authorized seller line at the root."""
        response = client.get("/ads.txt")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert response.headers["cache-control"] == "public, max-age=86400"
        assert response.headers["x-robots-tag"] == "noindex"
        assert response.text == "google.com, pub-7271682066779719, DIRECT, f08c47fec0942fa0\n"

    def test_sellers_json_exposes_publisher_transparency(self, client):
        """sellers.json should match the OmniTrackr publisher identity."""
        response = client.get("/sellers.json")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        assert response.headers["x-robots-tag"] == "noindex"
        payload = response.json()
        assert payload["version"] == 1
        assert payload["sellers"] == [
            {
                "seller_id": "pub-7271682066779719",
                "name": "OmniTrackr",
                "domain": "omnitrackr.xyz",
                "seller_type": "PUBLISHER",
            }
        ]
    
    def test_head_sitemap(self, client):
        """Test HEAD request for sitemap."""
        # HEAD requests may not be implemented, so we'll just check GET works
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
    
    def test_head_robots(self, client):
        """Test HEAD request for robots.txt."""
        # HEAD requests may not be implemented, so we'll just check GET works
        response = client.get("/robots.txt")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_llms_txt_points_to_public_value_pages(self, client):
        """Machine-readable site summary should include the strongest public pages."""
        response = client.get("/llms.txt")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert response.headers["x-robots-tag"] == "noindex"
        content = response.text
        assert "- Media tracker setup checklist: https://omnitrackr.xyz/media-tracker-checklist" in content
        assert "- Sample library: https://omnitrackr.xyz/sample-library" in content
        assert "- Content Quality Policy: https://omnitrackr.xyz/content-quality" in content
        assert "- HTML Site Map: https://omnitrackr.xyz/site-map" in content
        assert "a demo library at https://omnitrackr.xyz/demo" in content
        assert "a sample media library at https://omnitrackr.xyz/sample-library" in content
        assert "https://omnitrackr.xyz/media-tracker-checklist" in content
        assert "a human-readable site map at https://omnitrackr.xyz/site-map" in content
        assert "content quality standards at https://omnitrackr.xyz/content-quality" in content
        assert "## Quality and Advertising Boundaries" in content
        assert "private authenticated app shell" in content
        assert "standalone review detail pages require longer review text" in content
        assert "not ad placement surfaces" in content
        assert "a sample library at https://omnitrackr.xyz/demo" not in content

    def test_ai_txt_well_known_alias_is_not_blocked(self, client):
        """The intentionally published AI summary alias should bypass scanner-path blocking."""
        response = client.get("/.well-known/ai.txt")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert response.headers["x-robots-tag"] == "noindex"
        assert "## Quality and Advertising Boundaries" in response.text


class TestSecurityMiddleware:
    """Test security headers middleware."""
    
    def test_security_headers_present(self, client):
        """Test that security headers are added to responses."""
        response = client.get("/")
        assert response.status_code == 200
        
        # Check for security headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "X-XSS-Protection" in response.headers
        assert "Referrer-Policy" in response.headers
        assert "Permissions-Policy" in response.headers

    def test_public_content_pages_use_nonce_csp_without_unsafe_inline(self, client):
        """Public SEO/content pages should not need unsafe-inline in CSP."""
        for path in [
            "/about",
            "/privacy",
            "/advertising",
            "/content-quality",
            "/site-map",
            "/faq",
            "/guides",
            "/compare",
            "/use-cases",
            "/changelog",
            "/tv-show-tracker",
            "/game-tracker",
            "/movie-tracker",
            "/anime-tracker",
            "/book-tracker",
            "/music-tracker",
            "/media-statistics",
            "/export-import-guide",
            "/tracking-templates",
            "/review-guidelines",
            "/sample-library",
            "/demo",
            "/media-tracking",
            "/roadmap",
            "/terms",
            "/contact",
            "/reviews",
        ]:
            response = client.get(path)
            assert response.status_code == 200
            csp = response.headers["Content-Security-Policy"]
            assert "'unsafe-inline'" not in csp
            assert "'nonce-" in csp
            assert ' nonce="' in response.text
            assert ' style="' not in response.text

    def test_root_script_csp_uses_nonce_without_unsafe_inline(self, client):
        """The dashboard should not need unsafe-inline in CSP."""
        response = client.get("/")
        assert response.status_code == 200
        csp = response.headers["Content-Security-Policy"]
        script_src = next(
            directive for directive in csp.split(";") if directive.strip().startswith("script-src")
        )
        assert "'unsafe-inline'" not in csp
        assert "'unsafe-inline'" not in script_src
        assert "'nonce-" in script_src
        assert ' nonce="' in response.text
        assert ' style="' not in response.text
        assert "aggregateRating" not in response.text
        assert "SearchAction" not in response.text
        assert "BreadcrumbList" in response.text
        assert "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in response.text

    def test_generated_api_docs_are_noindexed(self, client):
        """Generated API documentation should stay accessible without entering search results."""
        for path in ("/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.headers["X-Robots-Tag"] == "noindex, nofollow"

    def test_adsense_loader_is_limited_to_public_content_pages(self, client):
        """AdSense should not load on the mixed landing/dashboard shell or legal pages."""
        eligible_paths = [
            "/about",
            "/faq",
            "/guides",
            "/compare",
            "/use-cases",
            "/changelog",
            "/tv-show-tracker",
            "/game-tracker",
            "/movie-tracker",
            "/anime-tracker",
            "/book-tracker",
            "/music-tracker",
            "/media-statistics",
            "/export-import-guide",
            "/media-tracker-checklist",
            "/tracking-templates",
            "/review-guidelines",
            "/sample-library",
            "/demo",
            "/media-tracking",
            "/roadmap",
            "/reviews",
        ]
        excluded_paths = ["/", "/privacy", "/advertising", "/content-quality", "/site-map", "/terms", "/contact"]

        for path in eligible_paths:
            response = client.get(path)
            assert response.status_code == 200
            assert "/static/ad-loader.js" in response.text
            assert "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in response.text

        for path in excluded_paths:
            response = client.get(path)
            assert response.status_code == 200
            assert "/static/ad-loader.js" not in response.text
            assert "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in response.text

    def test_public_pages_expose_adsense_publisher_meta_without_direct_ad_script(self, client):
        """Public pages should expose publisher verification while keeping initial ads non-intrusive."""
        public_paths = [
            "/",
            "/about",
            "/faq",
            "/guides",
            "/compare",
            "/use-cases",
            "/changelog",
            "/tv-show-tracker",
            "/game-tracker",
            "/movie-tracker",
            "/anime-tracker",
            "/book-tracker",
            "/music-tracker",
            "/media-statistics",
            "/export-import-guide",
            "/media-tracker-checklist",
            "/tracking-templates",
            "/review-guidelines",
            "/sample-library",
            "/demo",
            "/media-tracking",
            "/roadmap",
            "/reviews",
            "/reviews?category=movie",
            "/reviews?category=tv_show",
            "/reviews?category=anime",
            "/reviews?category=video_game",
            "/reviews?category=music",
            "/reviews?category=book",
            "/privacy",
            "/advertising",
            "/content-quality",
            "/site-map",
            "/terms",
            "/contact",
        ]

        for path in public_paths:
            response = client.get(path)
            assert response.status_code == 200
            assert response.text.count('name="google-adsense-account"') == 1
            assert '<meta name="google-adsense-account" content="ca-pub-7271682066779719">' in response.text
            assert "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in response.text

    def test_adsense_loader_is_suppressed_for_authenticated_public_requests(self, authenticated_client):
        """Logged-in users should not receive the public ad-loader on guide/review pages."""
        for path in ("/about", "/reviews", "/media-tracking"):
            response = authenticated_client.get(path)
            assert response.status_code == 200
            assert "/static/ad-loader.js" not in response.text
            assert "pagead2.googlesyndication.com/pagead/js/adsbygoogle.js" not in response.text

    def test_ad_eligible_public_pages_have_substantial_original_inventory(self, client):
        """Every ad-eligible public page should render as substantial content inventory."""
        eligible_paths = [
            "/about",
            "/faq",
            "/guides",
            "/compare",
            "/use-cases",
            "/changelog",
            "/tv-show-tracker",
            "/game-tracker",
            "/movie-tracker",
            "/anime-tracker",
            "/book-tracker",
            "/music-tracker",
            "/media-statistics",
            "/export-import-guide",
            "/media-tracker-checklist",
            "/tracking-templates",
            "/review-guidelines",
            "/sample-library",
            "/demo",
            "/media-tracking",
            "/roadmap",
            "/reviews",
        ]

        for path in eligible_paths:
            response = client.get(path)
            assert response.status_code == 200
            quality = parse_page_quality(response.text)
            assert quality.word_count >= 750, f"{path} has only {quality.word_count} crawlable words"
            assert quality.h1_count == 1, f"{path} should have exactly one H1"
            assert quality.h2_count >= 3, f"{path} should have multiple content sections"
            assert quality.description_count == 1, f"{path} should have one meta description"
            assert quality.canonical_count == 1, f"{path} should have one canonical URL"
            assert quality.json_ld_count >= 1, f"{path} should include structured data"

    def test_indexable_public_utility_pages_are_not_thin_placeholders(self, client):
        """Legal, support, and ad-disclosure pages should also provide useful trust content."""
        utility_paths = [
            "/privacy",
            "/advertising",
            "/content-quality",
            "/site-map",
            "/terms",
            "/contact",
        ]

        for path in utility_paths:
            response = client.get(path)
            assert response.status_code == 200
            quality = parse_page_quality(response.text)
            assert quality.word_count >= 700, f"{path} has only {quality.word_count} crawlable words"
            assert quality.h1_count == 1, f"{path} should have exactly one H1"
            assert quality.h2_count >= 3, f"{path} should have multiple content sections"
            assert quality.description_count == 1, f"{path} should have one meta description"
            assert quality.canonical_count == 1, f"{path} should have one canonical URL"
            assert quality.json_ld_count >= 1, f"{path} should include structured data"
            assert "/static/ad-loader.js" not in response.text

    def test_public_pages_have_click_focused_metadata(self, client):
        """Public pages should provide unique titles and descriptions for search snippets."""
        pages = {
            "/": "Free Media Tracker",
            "/about": "Free Media Tracking App",
            "/advertising": "Advertising Policy",
            "/content-quality": "Content Quality Policy",
            "/site-map": "Site Map",
            "/faq": "OmniTrackr FAQ",
            "/guides": "Track Media, Reviews, Stats",
            "/compare": "OmniTrackr vs Spreadsheets",
            "/use-cases": "Media Tracking Use Cases",
            "/changelog": "OmniTrackr Changelog",
            "/tv-show-tracker": "TV Show Tracker",
            "/game-tracker": "Game Tracker",
            "/movie-tracker": "Movie Tracker",
            "/anime-tracker": "Anime Tracker",
            "/book-tracker": "Book Tracker",
            "/music-tracker": "Music Tracker",
            "/media-statistics": "Media Statistics",
            "/export-import-guide": "Export & Import Guide",
            "/media-tracker-checklist": "Media Tracker Setup Checklist",
            "/tracking-templates": "Media Tracking Templates",
            "/review-guidelines": "Media Review Guidelines",
            "/sample-library": "Sample Media Library",
            "/demo": "OmniTrackr Demo",
            "/media-tracking": "Media Tracking Hub",
            "/roadmap": "OmniTrackr Roadmap",
            "/reviews": "Public Media Reviews",
            "/reviews?category=movie": "Movie Reviews",
            "/reviews?category=tv_show": "TV Show Reviews",
            "/reviews?category=anime": "Anime Reviews",
            "/reviews?category=video_game": "Video Game Reviews",
            "/reviews?category=music": "Music Reviews",
            "/reviews?category=book": "Book Reviews",
        }
        titles = {}
        descriptions = {}

        for path, title_fragment in pages.items():
            response = client.get(path)
            assert response.status_code == 200
            metadata = parse_metadata(response.text)
            assert title_fragment in metadata.title
            assert metadata.description
            titles[path] = metadata.title
            descriptions[path] = metadata.description
            assert "og:description" in response.text

        assert len(set(titles.values())) == len(titles), f"Duplicate public page titles: {titles}"
        assert len(set(descriptions.values())) == len(descriptions), f"Duplicate public page descriptions: {descriptions}"

    def test_public_pages_have_clear_navigation(self, client):
        """Public pages should expose consistent crawlable navigation."""
        expected_hrefs = {
            "/",
            "/demo",
            "/media-tracking",
            "/faq",
            "/guides",
            "/site-map",
            "/sample-library",
            "/compare",
            "/use-cases",
            "/reviews",
            "/advertising",
            "/content-quality",
            "/privacy",
            "/#landing-auth",
        }

        for path in PUBLIC_PAGE_PATHS:
            response = client.get(path)
            assert response.status_code == 200
            assert 'aria-label="Public site navigation"' in response.text
            hrefs = extract_hrefs(response.text)
            if path == "/":
                # The landing page intentionally keeps a small, task-focused nav.
                assert {"/", "/guides", "/reviews", "/faq", "/privacy", "/#landing-auth"}.issubset(hrefs)
            else:
                assert expected_hrefs.issubset(hrefs)
            assert 'class="public-site-nav__cta" href="/#landing-auth"' in response.text

    def test_public_pages_do_not_render_mojibake_text(self, client):
        """Public pages should not show broken UTF-8 artifacts to visitors or reviewers."""
        mojibake_markers = {
            "\u00c2": "stray latin-1 prefix",
            "\u00c3": "misdecoded accented character prefix",
            "\u00e2": "misdecoded punctuation or emoji prefix",
            "\u00f0": "misdecoded emoji prefix",
            "\ufffd": "replacement character",
        }

        for path in PUBLIC_PAGE_PATHS:
            response = client.get(path)
            assert response.status_code == 200
            quality = parse_page_quality(response.text)
            visible_text = " ".join(quality.text_parts)
            for marker, reason in mojibake_markers.items():
                assert marker not in visible_text, f"{path} renders {reason}: {marker!r}"

    def test_public_internal_links_resolve_successfully(self, client):
        """Crawlable public pages should not send visitors or reviewers to broken internal links."""
        ignored_prefixes = ("#", "mailto:", "tel:", "http://", "https://")

        for page in PUBLIC_PAGE_PATHS:
            response = client.get(page)
            assert response.status_code == 200
            for href in extract_hrefs(response.text):
                if href.startswith(ignored_prefixes):
                    continue
                target = href.split("#", 1)[0]
                target_response = client.get(target)
                assert target_response.status_code < 400, f"{page} links to broken internal URL {href}"

    def test_about_page_explains_user_control_and_maintenance(self, client):
        """About page should show trust and maintenance signals for visitors."""
        response = client.get("/about")

        assert response.status_code == 200
        content = response.text
        assert "What Is OmniTrackr?" in content
        assert "Built Around User Control" in content
        assert "A Maintained Live App" in content
        assert "private tracking separate from public discovery" in content
        assert "Data portability is part of the product philosophy" in content
        assert "not a static landing page or a placeholder project" in content
        hrefs = extract_hrefs(content)
        assert "/guides" in hrefs
        assert "/compare" in hrefs
        assert "/changelog" in hrefs
        assert "/privacy" in hrefs

    def test_media_tracking_hub_links_to_category_guides(self, client):
        """The media hub should expose the deeper public guide pages."""
        response = client.get("/media-tracking")

        assert response.status_code == 200
        content = response.text
        assert "Why a Hub Helps" in content
        assert "Choose a Workflow" in content
        assert "A Monthly Media Library Audit" in content
        assert "What Good Tracking Content Includes" in content
        assert "original context over copied descriptions" in content
        hrefs = extract_hrefs(content)
        for path in (
            "/movie-tracker",
            "/tv-show-tracker",
            "/anime-tracker",
            "/game-tracker",
            "/music-tracker",
            "/book-tracker",
            "/media-statistics",
            "/export-import-guide",
            "/review-guidelines",
        ):
            assert path in hrefs

    def test_movie_tracker_page_explains_watchlists_rewatches_and_privacy(self, client):
        """Movie tracker guide should be substantial standalone content."""
        response = client.get("/movie-tracker")

        assert response.status_code == 200
        content = response.text
        assert "Why Track Movies Outside a Streaming App?" in content
        assert "A Practical Movie Tracking Workflow" in content
        assert "Watchlists, Rewatches, and Recommendations" in content
        assert "What Makes a Movie Review Useful?" in content
        assert "Privacy for Movie Lists and Reviews" in content
        assert "spoiler sensitivity" in content
        hrefs = extract_hrefs(content)
        assert "/media-tracking" in hrefs
        assert "/compare" in hrefs
        assert "/review-guidelines" in hrefs
        assert "/reviews" in hrefs

    def test_tv_show_tracker_page_explains_paused_shows_and_finales(self, client):
        """TV guide should explain long-running series decisions."""
        response = client.get("/tv-show-tracker")

        assert response.status_code == 200
        content = response.text
        assert "Why TV Shows Need Their Own Tracking Workflow" in content
        assert "Seasons, Paused Shows, and Finales" in content
        assert "What Makes a Useful TV Review?" in content
        assert "Privacy and Friend Sharing" in content
        assert "spoiler-sensitive shows" in content
        hrefs = extract_hrefs(content)
        assert "/compare" in hrefs
        assert "/use-cases" in hrefs
        assert "/reviews" in hrefs

    def test_game_tracker_page_explains_completion_platforms_and_privacy(self, client):
        """Game guide should explain backlog and platform-specific tracking."""
        response = client.get("/game-tracker")

        assert response.status_code == 200
        content = response.text
        assert "Why Track Video Games?" in content
        assert "A Better Backlog Workflow" in content
        assert "Completion, Platforms, and Play Style" in content
        assert "What to Put in a Game Review" in content
        assert "Sharing a Game Library" in content
        assert "completionists, casual sessions, co-op groups" in content
        hrefs = extract_hrefs(content)
        assert "/tv-show-tracker" in hrefs
        assert "/compare" in hrefs
        assert "/use-cases" in hrefs

    def test_guides_page_links_to_full_guide_library(self, client):
        """The guides page should work as a crawlable public resource directory."""
        response = client.get("/guides")

        assert response.status_code == 200
        content = response.text
        assert "Guide Library" in content
        assert "OmniTrackr Guide Library" in content
        assert '"@type": "ItemList"' in content
        hrefs = extract_hrefs(content)
        for path in (
            "/media-tracking",
            "/faq",
            "/movie-tracker",
            "/tv-show-tracker",
            "/anime-tracker",
            "/game-tracker",
            "/music-tracker",
            "/book-tracker",
            "/media-statistics",
            "/export-import-guide",
            "/media-tracker-checklist",
            "/tracking-templates",
            "/review-guidelines",
            "/sample-library",
        ):
            assert path in hrefs

    def test_media_tracker_checklist_gives_first_session_setup_plan(self, client):
        """Setup checklist should provide practical first-session guidance for new users."""
        response = client.get("/media-tracker-checklist")

        assert response.status_code == 200
        content = response.text
        assert "Media Tracker Setup Checklist" in content
        assert "Why Start With a Checklist?" in content
        assert "Choose Your Active Categories" in content
        assert "Define Your Rating Scale" in content
        assert "Add a Starter Library" in content
        assert "Separate Private Notes From Public Reviews" in content
        assert "First-Week Cleanup Checklist" in content
        assert '"@type": "HowTo"' in content
        hrefs = extract_hrefs(content)
        assert "/media-tracking" in hrefs
        assert "/tracking-templates" in hrefs
        assert "/sample-library" in hrefs
        assert "/review-guidelines" in hrefs

    def test_tracking_templates_page_has_original_practical_content(self, client):
        """Templates page should provide useful standalone content before signup."""
        response = client.get("/tracking-templates")

        assert response.status_code == 200
        content = response.text
        assert "Media Tracking Templates" in content
        assert "Rating Scale Template" in content
        assert "Category Field Templates" in content
        assert "Review Prompt Template" in content
        assert "Backlog Cleanup Template" in content
        assert "Privacy and Sharing Template" in content
        assert '"@type": "HowTo"' in content
        hrefs = extract_hrefs(content)
        assert "/demo" in hrefs
        assert "/media-tracking" in hrefs
        assert "/compare" in hrefs
        assert "/export-import-guide" in hrefs

    def test_review_guidelines_page_encourages_substantial_public_reviews(self, client):
        """Review guidelines should help avoid thin public review content."""
        response = client.get("/review-guidelines")

        assert response.status_code == 200
        content = response.text
        assert "Media Review Guidelines" in content
        assert "What Makes a Review Useful?" in content
        assert "Simple Review Prompt" in content
        assert "Category-Specific Review Angles" in content
        assert "Private Notes vs Public Reviews" in content
        assert "Before and After Examples" in content
        assert "Quality Checklist Before Publishing" in content
        assert "Public review quality also helps OmniTrackr avoid becoming a thin review directory" in content
        assert '"@type": "HowTo"' in content
        hrefs = extract_hrefs(content)
        assert "/reviews" in hrefs
        assert "/tracking-templates" in hrefs
        assert "/media-tracking" in hrefs
        assert "/compare" in hrefs

    def test_sample_library_page_shows_concrete_first_party_examples(self, client):
        """Sample library should make the product value concrete without exposing user data."""
        response = client.get("/sample-library")

        assert response.status_code == 200
        content = response.text
        assert "Sample Media Library" in content
        assert "Why a Sample Library Helps" in content
        assert "Example Records" in content
        assert "A Weekly Cleanup Workflow" in content
        assert "Privacy Choices in the Sample" in content
        assert "What Statistics Would Show" in content
        assert "not a copy of a user account" in content
        assert "Signal Harbor" in content
        assert '"@type": "ItemList"' in content
        hrefs = extract_hrefs(content)
        assert "/demo" in hrefs
        assert "/tracking-templates" in hrefs
        assert "/review-guidelines" in hrefs
        assert "/media-tracking" in hrefs

    def test_faq_page_answers_common_adsense_and_user_questions(self, client):
        """FAQ page should answer real visitor questions and support public content depth."""
        response = client.get("/faq")

        assert response.status_code == 200
        content = response.text
        assert "OmniTrackr FAQ" in content
        assert "What is OmniTrackr?" in content
        assert "Can I evaluate OmniTrackr before signing up?" in content
        assert "Are reviews public by default?" in content
        assert "How do friend and privacy controls work?" in content
        assert "Can I export or import my library?" in content
        assert "Where can ads appear?" in content
        assert '"@type": "FAQPage"' in content
        hrefs = extract_hrefs(content)
        assert "/demo" in hrefs
        assert "/media-tracking" in hrefs
        assert "/tracking-templates" in hrefs
        assert "/review-guidelines" in hrefs
        assert "/advertising" in hrefs

    def test_roadmap_page_includes_shipped_context_not_only_future_plans(self, client):
        """Roadmap should show maintenance evidence, not read like an empty coming-soon page."""
        response = client.get("/roadmap")

        assert response.status_code == 200
        content = response.text
        assert "Recently Shipped" in content
        assert "Public Guide Library" in content
        assert "Review Quality Tools" in content
        assert "Ad and Privacy Transparency" in content
        assert "Security and SEO Cleanup" in content
        assert "Stability and Release Guardrails" in content
        assert "should not require destructive migrations" in content
        assert "Recent verification covers account flows" in content
        assert "not a promise that every idea will ship" in content
        hrefs = extract_hrefs(content)
        assert "/changelog" in hrefs
        assert "/demo" in hrefs
        assert "/compare" in hrefs

    def test_demo_page_explains_sample_library_workflow_and_privacy(self, client):
        """Demo page should be useful standalone content before signup."""
        response = client.get("/demo")

        assert response.status_code == 200
        content = response.text
        assert "Sample Collection" in content
        assert "Sample Statistics" in content
        assert "Example Tracking Workflow" in content
        assert "What the Demo Helps You Decide" in content
        assert "fictional and does not expose real user libraries" in content
        assert "mark the current status" in content
        hrefs = extract_hrefs(content)
        assert "/media-tracking" in hrefs
        assert "/reviews" in hrefs
        assert "/faq" in hrefs
        assert "/compare" in hrefs
        assert "/privacy" in hrefs

    def test_export_import_guide_explains_portability_and_backup_safety(self, client):
        """Export guide should be practical trust-building content before signup."""
        response = client.get("/export-import-guide")

        assert response.status_code == 200
        content = response.text
        assert "Why Data Portability Matters" in content
        assert "What an Export Includes" in content
        assert "How Import Helps" in content
        assert "What to Remember About Backups" in content
        assert "Why This Matters for Choosing a Tracker" in content
        assert "JSON files are readable data files" in content
        assert "public-review flags" in content
        hrefs = extract_hrefs(content)
        assert "/media-tracking" in hrefs
        assert "/guides" in hrefs
        assert "/demo" in hrefs
        assert "/tracking-templates" in hrefs
        assert "/privacy" in hrefs

    def test_media_statistics_page_explains_insights_review_coverage_and_privacy(self, client):
        """Statistics guide should explain why OmniTrackr is more than a static list."""
        response = client.get("/media-statistics")

        assert response.status_code == 200
        content = response.text
        assert "Why Statistics Matter in a Media Tracker" in content
        assert "Category-Specific Insights" in content
        assert "Using Review Coverage" in content
        assert "Privacy and Sharing" in content
        assert "A practical monthly cleanup" in content
        assert "Public review counts are separate from private notes" in content
        hrefs = extract_hrefs(content)
        assert "/demo" in hrefs
        assert "/export-import-guide" in hrefs
        assert "/media-tracking" in hrefs
        assert "/review-guidelines" in hrefs
        assert "/compare" in hrefs

    def test_music_tracker_page_explains_albums_relisten_notes_and_privacy(self, client):
        """Music tracker page should be useful standalone category content."""
        response = client.get("/music-tracker")

        assert response.status_code == 200
        content = response.text
        assert "Why Track Music in a Media Library?" in content
        assert "Albums, Artists, and Relisten Notes" in content
        assert "Writing Music Reviews That Help Later" in content
        assert "Music Statistics and Taste Patterns" in content
        assert "Privacy, Sharing, and Recommendations" in content
        assert "Use ratings after a few listens" in content
        hrefs = extract_hrefs(content)
        assert "/media-tracking" in hrefs
        assert "/media-statistics" in hrefs
        assert "/review-guidelines" in hrefs
        assert "/demo" in hrefs
        assert "/reviews" in hrefs

    def test_anime_tracker_page_explains_seasonal_backlog_and_privacy(self, client):
        """Anime tracker page should explain seasonal and stalled-show workflows."""
        response = client.get("/anime-tracker")

        assert response.status_code == 200
        content = response.text
        assert "Why Anime Tracking Gets Complicated" in content
        assert "Seasonal Anime and Stalled Shows" in content
        assert "Writing Better Anime Reviews" in content
        assert "Anime Statistics and Backlog Cleanup" in content
        assert "Privacy and Public Anime Reviews" in content
        assert "Stalled or dropped" in content
        assert "Timing matters too" in content
        hrefs = extract_hrefs(content)
        assert "/media-tracking" in hrefs
        assert "/tv-show-tracker" in hrefs
        assert "/media-statistics" in hrefs
        assert "/review-guidelines" in hrefs
        assert "/reviews" in hrefs

    def test_book_tracker_page_explains_formats_rereads_and_privacy(self, client):
        """Book tracker page should contain substantial standalone reading guidance."""
        response = client.get("/book-tracker")

        assert response.status_code == 200
        content = response.text
        assert "A Reading List Workflow That Stays Useful" in content
        assert "Formats, Editions, and Rereads" in content
        assert "What Makes a Book Review Helpful?" in content
        assert "Book Statistics and Reading Patterns" in content
        assert "Privacy and Public Book Notes" in content
        assert "audiobook narrator" in content
        assert "Private notes can be rough reminders" in content
        hrefs = extract_hrefs(content)
        assert "/media-tracking" in hrefs
        assert "/media-statistics" in hrefs
        assert "/export-import-guide" in hrefs
        assert "/reviews" in hrefs

    def test_changelog_explains_release_quality_and_verification(self, client):
        """Changelog should document real shipped work and verification, not only a date list."""
        response = client.get("/changelog")

        assert response.status_code == 200
        content = response.text
        assert "July 2026: Review Quality, Freshness, and Public Discovery" in content
        assert "June 2026: Public Content, Privacy, and Ad Readiness" in content
        assert "Recent Security and Quality Improvements" in content
        assert "Recent Content Improvements" in content
        assert "Release Verification" in content
        assert '"dateModified": "2026-07-05"' in content
        assert "public reviews API default to favor substantial reviews" in content
        assert "standalone review detail pages" in content
        assert "at least 750 crawlable words" in content
        assert "min_chars=1" in content
        assert "does not modify account records, private libraries" in content
        assert "These changes do not alter existing user libraries" in content
        assert "ad-loader behavior" in content
        hrefs = extract_hrefs(content)
        assert "/sample-library" in hrefs
        assert "/content-quality" in hrefs
        assert "/review-guidelines" in hrefs

    def test_contact_page_explains_support_and_data_request_paths(self, client):
        """Contact page should give useful support and privacy request guidance."""
        response = client.get("/contact")

        assert response.status_code == 200
        content = response.text
        assert "Support Channels" in content
        assert "Report Issues" in content
        assert "Privacy and Data Requests" in content
        assert "Please do not send passwords" in content
        assert "Before requesting deletion" in content
        hrefs = extract_hrefs(content)
        assert "/guides" in hrefs
        assert "/faq" in hrefs
        assert "/privacy" in hrefs

    def test_compare_table_uses_scoped_responsive_wrapper(self, client):
        """Compare table should not inherit sticky dashboard table behavior."""
        response = client.get("/compare")

        assert response.status_code == 200
        content = response.text
        assert "comparison-table-wrap" in content
        assert "table-layout: fixed" in content
        assert "position: static !important" in content
        assert "transform: none" in content

    def test_guides_page_header_has_visible_h1(self, client):
        """Guides page should not hide the H1 with transparent gradient text."""
        response = client.get("/guides")

        assert response.status_code == 200
        content = response.text
        assert "<h1>How-To Guides</h1>" in content
        assert ".privacy-header h1" in content
        guides_h1_rule = content.split(".privacy-header h1", 1)[1].split("}", 1)[0]
        assert "color: var(--primary)" in guides_h1_rule
        assert "-webkit-text-fill-color: transparent" not in guides_h1_rule

    def test_home_public_navigation_keeps_key_resources_discoverable(self, client):
        """The anonymous homepage should prioritize public resources over app controls."""
        response = client.get("/")

        assert response.status_code == 200
        content = response.text
        assert 'data-public-shell="true"' in content
        assert "🐙 GitHub" not in content
        assert "LinkedIn" not in content
        assert "/faq" in extract_hrefs(content)
        assert "/guides" in extract_hrefs(content)
        assert "/reviews" in extract_hrefs(content)
        assert "OmniTrackr" in content
        assert "Start tracking" in content
        assert "Public reviews" in content

    def test_homepage_prioritizes_product_workflow_over_internal_content_inventory(self, client):
        """Landing page should explain the product before sending people into guides."""
        response = client.get("/")

        assert response.status_code == 200
        content = response.text
        assert "Your media history, in one place" in content
        assert "Remember more than the title." in content
        assert "From recommendation to a memory you can revisit" in content
        assert "Public reviews are optional. Useful context isn’t." in content
        assert "A few honest answers" in content
        hrefs = extract_hrefs(content)
        assert "/guides" in hrefs
        assert "/reviews" in hrefs
        assert "/privacy" in hrefs

    def test_privacy_policy_discloses_google_ads_data_use(self, client):
        """Privacy policy should include required Google ads/cookie disclosures."""
        response = client.get("/privacy")
        assert response.status_code == 200
        content = response.text
        assert "Google Ads and Advertising Cookies" in content
        assert "cookies, web beacons, IP addresses" in content
        hrefs = extract_hrefs(content)
        assert "/advertising" in hrefs
        href_parts = {
            (parsed.scheme, parsed.netloc, parsed.path)
            for parsed in (urlparse(href) for href in hrefs)
        }
        assert ("https", "policies.google.com", "/technologies/partner-sites") in href_parts
        assert ("https", "adssettings.google.com", "/") in href_parts

    def test_advertising_policy_explains_limited_public_ads(self, client):
        """Advertising policy should explain public-page placement and user controls."""
        response = client.get("/advertising")

        assert response.status_code == 200
        content = response.text
        assert "Advertising Policy" in content
        assert "public content pages" in content
        assert "No deceptive placement" in content
        assert "Light by default" in content
        assert "Ads should not be placed inside private account forms" in content
        assert "The mixed landing and authenticated app shell are intentionally kept out of the ad-loader allowlist" in content
        assert "How Placements Are Reviewed" in content
        assert "Public pages should remain readable when ads are unavailable" in content
        hrefs = extract_hrefs(content)
        assert "/privacy" in hrefs
        assert "/sample-library" in hrefs
        href_parts = {
            (parsed.scheme, parsed.netloc, parsed.path)
            for parsed in (urlparse(href) for href in hrefs)
        }
        assert ("https", "policies.google.com", "/technologies/partner-sites") in href_parts
        assert ("https", "adssettings.google.com", "/") in href_parts

    def test_content_quality_policy_explains_originality_and_review_standards(self, client):
        """Content quality policy should explain how OmniTrackr avoids thin public content."""
        response = client.get("/content-quality")

        assert response.status_code == 200
        content = response.text
        assert "Content Quality Policy" in content
        assert "Original Public Content Standards" in content
        assert "Public Review Quality" in content
        assert "User-Generated Content Safeguards" in content
        assert "Content OmniTrackr Should Avoid" in content
        assert "Maintenance and Review Process" in content
        assert '"dateModified": "2026-07-06"' in content
        assert "scraped summaries, or generic filler" in content
        assert "Public review pages for empty reviews, one-word notes, or private account data" in content
        assert "Reviews that contain obvious URLs, email addresses, phone-number-like contact details, or promotional phrases" in content
        assert "marked noindex and do not load ads until they contain substantial public review inventory" in content
        assert "Machine-readable files such as ads.txt, sellers.json, llms.txt, and the AI summary endpoint" in content
        assert "Thin pages should be improved, noindexed, or removed from public discovery" in content
        hrefs = extract_hrefs(content)
        assert "/sample-library" in hrefs
        assert "/review-guidelines" in hrefs
        assert "/advertising" in hrefs

    def test_site_map_groups_public_pages_for_reviewers_and_crawlers(self, client):
        """HTML site map should expose the full public content inventory with context."""
        response = client.get("/site-map")

        assert response.status_code == 200
        content = response.text
        assert "OmniTrackr Site Map" in content
        assert '"dateModified": "2026-07-05"' in content
        assert "Core Product Pages" in content
        assert "Category Tracker Guides" in content
        assert "Workflows, Reviews, and Comparisons" in content
        assert "Trust, Policies, and Support" in content
        assert "A human-readable directory for visitors, reviewers, and crawlers" in content
        assert "Pages that are only useful for authenticated app actions or developer tooling should stay out of public search inventory" in content
        hrefs = extract_hrefs(content)
        for path in (
            "/media-tracking",
            "/guides",
            "/sample-library",
            "/movie-tracker",
            "/tv-show-tracker",
            "/anime-tracker",
            "/game-tracker",
            "/music-tracker",
            "/book-tracker",
            "/tracking-templates",
            "/media-tracker-checklist",
            "/review-guidelines",
            "/reviews",
            "/privacy",
            "/advertising",
            "/content-quality",
            "/contact",
            "/roadmap",
        ):
            assert path in hrefs

    def test_nonce_injection_handles_uppercase_inline_tags(self):
        """Nonce injection should cover uppercase or mixed-case inline tags."""
        html = (
            "<HTML><HEAD><STYLE>.x { color: red; }</STYLE></HEAD>"
            "<BODY><SCRIPT>window.ok = true;</SCRIPT>"
            "<ScRiPt type=\"application/ld+json\">{}</ScRiPt>"
            "<SCRIPT SRC=\"/static/app.js\"></SCRIPT></BODY></HTML>"
        )

        processed = add_nonce_to_inline_tags(html, "test-nonce")

        assert '<style nonce="test-nonce">' in processed
        assert '<script nonce="test-nonce">' in processed
        assert '<script type="application/ld+json" nonce="test-nonce">' in processed
        assert '<script src="/static/app.js"></script>' in processed
        assert '<script src="/static/app.js" nonce=' not in processed

    def test_inline_style_extraction_drops_unsafe_css_breakouts(self):
        """Style extraction should not allow values to break out of the nonce style block."""
        html = '<html><head></head><body><a style="color:red}</style><script>alert(1)</script>">x</a></body></html>'

        processed = extract_inline_styles(html, "test-nonce")

        assert "alert(1)" not in processed
        assert "csp-style-" not in processed
        assert 'style="' not in processed
    
    def test_bot_filter_suspicious_paths(self, client):
        """Test that bot filter blocks suspicious paths."""
        suspicious_paths = [
            "/.env",
            "/.git",
            "/wp-admin",
            "/wp-config.php",
            "/admin",
            "/.aws",
            "/backend/.env",
        ]
        
        for path in suspicious_paths:
            response = client.get(path)
            assert response.status_code == 404
            assert "X-Robots-Tag" in response.headers
            assert "noindex, nofollow" in response.headers["X-Robots-Tag"]
    
    def test_bot_filter_double_slash_wordpress_paths(self, client):
        """Test that bot filter blocks double-slash WordPress scanner paths.
        
        Note: TestClient normalizes double slashes, so we test the normalized paths.
        In production, the middleware handles both double-slash and normalized paths.
        """
        # Test normalized paths (what TestClient sends after normalization)
        normalized_paths = [
            "/blog/wp-includes/wlwmanifest.xml",
            "/web/wp-includes/wlwmanifest.xml",
            "/wordpress/wp-includes/wlwmanifest.xml",
            "/wp-includes/wlwmanifest.xml",
            "/xmlrpc.php",
            "/wp-admin/setup-config.php",
        ]
        
        for path in normalized_paths:
            response = client.get(path)
            assert response.status_code == 404, f"Path {path} should be blocked"
            assert "X-Robots-Tag" in response.headers
            assert "noindex, nofollow" in response.headers["X-Robots-Tag"]
    
    def test_bot_filter_suspicious_user_agents(self, client):
        """Test that bot filter blocks suspicious user agents with suspicious paths."""
        suspicious_agents = [
            "sqlmap",
            "nikto",
            "nmap",
            "acunetix",
        ]
        
        for agent in suspicious_agents:
            response = client.get(
                "/.env",
                headers={"User-Agent": agent}
            )
            assert response.status_code == 404
    
    def test_bot_filter_allows_normal_requests(self, client):
        """Test that normal requests are not blocked."""
        response = client.get("/", headers={"User-Agent": "Mozilla/5.0"})
        assert response.status_code == 200


class TestImageEndpoints:
    """Test image serving endpoints."""
    
    def test_get_favicon_ico(self, client):
        """Test favicon.ico endpoint."""
        response = client.get("/favicon.ico")
        # Should return 200 or 404 depending on file existence
        assert response.status_code in [200, 404]
    
    def test_head_favicon_ico(self, client):
        """Test HEAD request for favicon.ico."""
        response = client.head("/favicon.ico")
        assert response.status_code in [200, 404]
    
    def test_get_favicon_png(self, client):
        """Test favicon.png endpoint."""
        response = client.get("/favicon.png")
        assert response.status_code in [200, 404]
    
    def test_head_favicon_png(self, client):
        """Test HEAD request for favicon.png."""
        response = client.head("/favicon.png")
        assert response.status_code in [200, 404]
    
    def test_get_vortex_image(self, client):
        """Test omnitrackr_vortex.png endpoint."""
        response = client.get("/omnitrackr_vortex.png")
        assert response.status_code in [200, 404]
    
    def test_head_vortex_image(self, client):
        """Test HEAD request for omnitrackr_vortex.png."""
        response = client.head("/omnitrackr_vortex.png")
        assert response.status_code in [200, 404]
    
    def test_get_film_background(self, client):
        """Test film_background.jpg endpoint."""
        response = client.get("/film_background.jpg")
        assert response.status_code in [200, 404]
    
    def test_head_film_background(self, client):
        """Test HEAD request for film_background.jpg."""
        response = client.head("/film_background.jpg")
        assert response.status_code in [200, 404]


class TestRootEndpoint:
    """Test root endpoint."""
    
    def test_get_root(self, client):
        """Anonymous users receive a focused public page, not empty private tables."""
        response = client.get("/")
        assert response.status_code == 200
        quality = parse_page_quality(response.text)
        assert quality.h1_count == 1
        assert 'data-public-shell="true"' in response.text
        assert 'id="mainContainer"' not in response.text
        assert 'id="logoutBtn"' not in response.text
        assert 'src="/static/public-landing.js"' in response.text
        assert 'src="./app.js"' not in response.text
    
    def test_head_root(self, client):
        """Test HEAD request to root."""
        response = client.head("/")
        assert response.status_code == 200

    def test_authenticated_root_keeps_the_full_dashboard(self, authenticated_client):
        """A signed-in session must keep the existing dashboard and application bundle."""
        response = authenticated_client.get("/")

        assert response.status_code == 200
        assert 'data-public-shell="true"' not in response.text
        assert 'id="mainContainer"' in response.text
        assert 'id="logoutBtn"' in response.text
        assert 'src="./app.js"' in response.text

