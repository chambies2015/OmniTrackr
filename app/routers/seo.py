"""
SEO endpoints for the OmniTrackr API.
"""
import os
import json
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .. import models
from ..dependencies import get_db

router = APIRouter(tags=["seo"])


@router.get("/sitemap.xml")
async def get_sitemap(db: Session = Depends(get_db)):
    """Generate and serve sitemap.xml for SEO."""
    base_url = os.getenv("SITE_URL", "https://omnitrackr.xyz")
    today = datetime.now().strftime('%Y-%m-%d')
    
    sitemap_parts = ["""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{base_url}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{base_url}/privacy</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{base_url}/reviews</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>""".format(base_url=base_url, today=today)]
    
    try:
        user_query = db.query(models.User.id).filter(
            and_(
                models.User.is_active == True,
                models.User.reviews_public == True
            )
        )
        
        review_limit = 500
        
        movie_reviews = db.query(models.Movie).filter(
            and_(
                models.Movie.review.isnot(None),
                models.Movie.review != "",
                models.Movie.user_id.in_(user_query)
            )
        ).limit(review_limit // 4).all()
        
        tv_reviews = db.query(models.TVShow).filter(
            and_(
                models.TVShow.review.isnot(None),
                models.TVShow.review != "",
                models.TVShow.user_id.in_(user_query)
            )
        ).limit(review_limit // 4).all()
        
        anime_reviews = db.query(models.Anime).filter(
            and_(
                models.Anime.review.isnot(None),
                models.Anime.review != "",
                models.Anime.user_id.in_(user_query)
            )
        ).limit(review_limit // 4).all()
        
        vg_reviews = db.query(models.VideoGame).filter(
            and_(
                models.VideoGame.review.isnot(None),
                models.VideoGame.review != "",
                models.VideoGame.user_id.in_(user_query)
            )
        ).limit(review_limit // 4).all()
        
        for review in movie_reviews:
            sitemap_parts.append(f"""  <url>
    <loc>{base_url}/reviews/{review.id}?category=movie</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")
        
        for review in tv_reviews:
            sitemap_parts.append(f"""  <url>
    <loc>{base_url}/reviews/{review.id}?category=tv_show</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")
        
        for review in anime_reviews:
            sitemap_parts.append(f"""  <url>
    <loc>{base_url}/reviews/{review.id}?category=anime</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")
        
        for review in vg_reviews:
            sitemap_parts.append(f"""  <url>
    <loc>{base_url}/reviews/{review.id}?category=video_game</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")
    except Exception:
        pass
    
    sitemap_parts.append("</urlset>")
    sitemap = "\n".join(sitemap_parts)
    
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
@router.head("/ads.txt")
async def get_ads_txt():
    """Serve ads.txt for Google AdSense verification."""
    publisher_id = os.getenv("ADSENSE_PUBLISHER_ID", "pub-7271682066779719")
    
    ads_txt = f"""google.com, {publisher_id}, DIRECT, f08c47fec0942fa0"""
    
    return Response(content=ads_txt, media_type="text/plain")


@router.get("/sellers.json")
async def get_sellers_json():
    """Serve sellers.json for ad transparency and verification."""
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


@router.get("/llms.txt")
@router.get("/.well-known/ai.txt")
async def get_llms_txt():
    """Serve llms.txt/ai.txt for AI model discovery and site understanding."""
    base_url = os.getenv("SITE_URL", "https://omnitrackr.xyz")
    
    llms_content = f"""# OmniTrackr - Media Collection Tracker

## About
OmniTrackr is a free web application for tracking and organizing movies, TV shows, anime, video games, music, and books. Users can rate, review, and analyze their media collection with comprehensive statistics, beautiful posters and cover art, and social features.

## Key Pages
- Home: {base_url}/
- Privacy Policy: {base_url}/privacy
- Public Reviews: {base_url}/reviews

## Features
- Track movies, TV shows, anime, video games, music, and books
- Rate and review media with detailed reviews
- Statistics dashboard with comprehensive analytics
- Export/import data in JSON format
- Automatic poster fetching from OMDB, Jikan, and RAWG APIs
- Friends and social features
- Real-time notifications
- Account management with privacy controls

## Content Types
- Movies: User reviews and ratings for films
- TV Shows: Reviews and ratings for television series
- Anime: Reviews and ratings for anime series
- Video Games: Reviews and ratings for video games

## Public Content
Public reviews are available at {base_url}/reviews and individual review pages at {base_url}/reviews/[id]?category=[category]

## Contact
Email: omnitrackr@gmail.com
Website: {base_url}
"""
    
    return Response(content=llms_content, media_type="text/plain")

