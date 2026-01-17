"""
SEO endpoints for the OmniTrackr API.
"""
import os
import json
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter(tags=["seo"])


@router.get("/sitemap.xml")
async def get_sitemap():
    """Generate and serve sitemap.xml for SEO."""
    base_url = os.getenv("SITE_URL", "https://omnitrackr.xyz")
    
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{base_url}/</loc>
    <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    
    return Response(content=sitemap, media_type="application/xml")


@router.get("/robots.txt")
async def get_robots():
    """Serve robots.txt for SEO."""
    site_url = os.getenv("SITE_URL", "https://omnitrackr.xyz")
    
    robots = f"""User-agent: Mediapartners-Google
Allow: /

User-agent: *
Disallow: /auth/
Disallow: /api/
Disallow: /static/credentials.js

Sitemap: {site_url}/sitemap.xml"""
    
    return Response(content=robots, media_type="text/plain")


@router.get("/ads.txt")
async def get_ads_txt():
    """Serve ads.txt for Google AdSense verification."""
    publisher_id = os.getenv("ADSENSE_PUBLISHER_ID", "pub-7271682066779719")
    
    ads_txt = f"""google.com, {publisher_id}, DIRECT, f08c47fec0942fa0"""
    
    return Response(content=ads_txt, media_type="text/plain")


@router.get("/sellers.json")
async def get_sellers_json():
    """Serve sellers.json for ad transparency and verification."""
    # Get Publisher ID from environment variable, or use placeholder
    publisher_id = os.getenv("ADSENSE_PUBLISHER_ID", "pub-7271682066779719")
    site_domain = os.getenv("SITE_DOMAIN", "omnitrackr.xyz")
    
    sellers_data = {
        "sellers": [
            {
                "seller_id": publisher_id,
                "name": "OmniTrackr",
                "domain": site_domain,
                "seller_type": "PUBLISHER"
            }
        ],
        "version": 1
    }
    
    return Response(
        content=json.dumps(sellers_data, indent=2),
        media_type="application/json"
    )

