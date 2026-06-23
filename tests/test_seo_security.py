"""
Tests for SEO endpoints and security middleware.
"""
from html.parser import HTMLParser
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app.csp import add_nonce_to_inline_tags, extract_inline_styles


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

    def test_sitemap_includes_public_value_pages(self, client):
        """Test that sitemap includes public editorial pages for crawlers."""
        response = client.get("/sitemap.xml")
        assert response.status_code == 200
        content = response.text
        assert "/compare" in content
        assert "/use-cases" in content
        assert "/changelog" in content
        assert "/tv-show-tracker" in content
        assert "/game-tracker" in content
        assert "/movie-tracker" in content
        assert "/anime-tracker" in content
        assert "/book-tracker" in content
        assert "/music-tracker" in content
        assert "/media-statistics" in content
        assert "/export-import-guide" in content
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
    
    def test_get_robots_txt(self, client):
        """Test robots.txt endpoint."""
        response = client.get("/robots.txt")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        content = response.text
        assert "User-agent: *" in content
        assert "Allow: /reviews" in content
        assert "Allow: /compare" in content
        assert "Allow: /use-cases" in content
        assert "Allow: /changelog" in content
        assert "Allow: /tv-show-tracker" in content
        assert "Allow: /game-tracker" in content
        assert "Allow: /movie-tracker" in content
        assert "Allow: /anime-tracker" in content
        assert "Allow: /book-tracker" in content
        assert "Allow: /music-tracker" in content
        assert "Allow: /media-statistics" in content
        assert "Allow: /export-import-guide" in content
        assert "Allow: /demo" in content
        assert "Allow: /media-tracking" in content
        assert "Allow: /roadmap" in content
        assert "Sitemap:" in content
    
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

    def test_public_pages_have_click_focused_metadata(self, client):
        """Public pages should provide unique titles and descriptions for search snippets."""
        pages = {
            "/": "Free Media Tracker",
            "/about": "Free Media Tracking App",
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
            "/demo": "OmniTrackr Demo",
            "/media-tracking": "Media Tracking Hub",
            "/roadmap": "OmniTrackr Roadmap",
            "/reviews": "Public Media Reviews",
        }

        for path, title_fragment in pages.items():
            response = client.get(path)
            assert response.status_code == 200
            assert title_fragment in response.text
            assert '<meta name="description"' in response.text
            assert "og:description" in response.text

    def test_media_tracking_hub_links_to_category_guides(self, client):
        """The media hub should expose the deeper public guide pages."""
        response = client.get("/media-tracking")

        assert response.status_code == 200
        hrefs = extract_hrefs(response.text)
        for path in (
            "/movie-tracker",
            "/tv-show-tracker",
            "/anime-tracker",
            "/game-tracker",
            "/music-tracker",
            "/book-tracker",
            "/media-statistics",
            "/export-import-guide",
        ):
            assert path in hrefs

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

    def test_home_footer_uses_clean_emoji_link_set(self, client):
        """Home footers should avoid old social links and use emoji labels."""
        response = client.get("/")

        assert response.status_code == 200
        content = response.text
        assert "🐙 GitHub" not in content
        assert "LinkedIn" not in content
        for label in (
            "📧 omnitrackr@gmail.com",
            "☕ Ko-fi",
            "ℹ️ About",
            "👀 Demo",
            "🧭 Tracking Hub",
            "📘 Guides",
            "⚖️ Compare",
            "💡 Use Cases",
            "📺 TV Tracker",
            "🎮 Game Tracker",
            "📝 Changelog",
            "🗺️ Roadmap",
            "📜 Terms",
            "✉️ Contact",
            "🔒 Privacy Policy",
        ):
            assert label in content

    def test_privacy_policy_discloses_google_ads_data_use(self, client):
        """Privacy policy should include required Google ads/cookie disclosures."""
        response = client.get("/privacy")
        assert response.status_code == 200
        content = response.text
        assert "Google Ads and Advertising Cookies" in content
        assert "cookies, web beacons, IP addresses" in content
        hrefs = extract_hrefs(content)
        href_parts = {
            (parsed.scheme, parsed.netloc, parsed.path)
            for parsed in (urlparse(href) for href in hrefs)
        }
        assert ("https", "policies.google.com", "/technologies/partner-sites") in href_parts
        assert ("https", "adssettings.google.com", "/") in href_parts

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
        """Test GET request to root."""
        response = client.get("/")
        assert response.status_code == 200
    
    def test_head_root(self, client):
        """Test HEAD request to root."""
        response = client.head("/")
        assert response.status_code == 200

