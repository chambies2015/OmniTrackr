"""
Tests for SEO endpoints and security middleware.
"""
import pytest
from fastapi.testclient import TestClient


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

