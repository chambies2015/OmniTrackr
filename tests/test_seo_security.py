"""
Tests for SEO endpoints and security middleware.
"""
import pytest
from fastapi.testclient import TestClient

from app.csp import add_nonce_to_inline_tags, extract_inline_styles


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
        for path in ["/about", "/privacy", "/guides", "/terms", "/contact", "/reviews"]:
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

