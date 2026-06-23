"""
SEO endpoints for the OmniTrackr API.
"""
import os
import json
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from .. import models
from ..dependencies import get_db

router = APIRouter(tags=["seo"])
PUBLIC_REVIEW_MIN_CHARS = int(os.getenv("PUBLIC_REVIEW_MIN_CHARS", "80"))


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
    <loc>{base_url}/about</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>{base_url}/guides</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>{base_url}/compare</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.75</priority>
  </url>
  <url>
    <loc>{base_url}/use-cases</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.75</priority>
  </url>
  <url>
    <loc>{base_url}/changelog</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.65</priority>
  </url>
  <url>
    <loc>{base_url}/tv-show-tracker</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.75</priority>
  </url>
  <url>
    <loc>{base_url}/game-tracker</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.75</priority>
  </url>
  <url>
    <loc>{base_url}/movie-tracker</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.75</priority>
  </url>
  <url>
    <loc>{base_url}/anime-tracker</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.75</priority>
  </url>
  <url>
    <loc>{base_url}/book-tracker</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.75</priority>
  </url>
  <url>
    <loc>{base_url}/music-tracker</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.75</priority>
  </url>
  <url>
    <loc>{base_url}/media-statistics</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.75</priority>
  </url>
  <url>
    <loc>{base_url}/export-import-guide</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.75</priority>
  </url>
  <url>
    <loc>{base_url}/demo</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>{base_url}/media-tracking</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>{base_url}/roadmap</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.65</priority>
  </url>
  <url>
    <loc>{base_url}/terms</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
  <url>
    <loc>{base_url}/contact</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>{base_url}/reviews</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>""".format(base_url=base_url, today=today)]
    
    try:
        user_query = db.query(models.User.id).filter(models.User.is_active == True)
        public_review_filter = lambda model_cls: and_(
            model_cls.review.isnot(None),
            model_cls.review != "",
            model_cls.review_public == True,
            func.length(func.trim(model_cls.review)) >= PUBLIC_REVIEW_MIN_CHARS,
            model_cls.user_id.in_(user_query)
        )
        
        review_limit = 600
        
        movie_reviews = db.query(models.Movie).filter(
            public_review_filter(models.Movie)
        ).limit(review_limit // 6).all()
        
        tv_reviews = db.query(models.TVShow).filter(
            public_review_filter(models.TVShow)
        ).limit(review_limit // 6).all()
        
        anime_reviews = db.query(models.Anime).filter(
            public_review_filter(models.Anime)
        ).limit(review_limit // 6).all()
        
        vg_reviews = db.query(models.VideoGame).filter(
            public_review_filter(models.VideoGame)
        ).limit(review_limit // 6).all()

        music_reviews = db.query(models.Music).filter(
            public_review_filter(models.Music)
        ).limit(review_limit // 6).all()

        book_reviews = db.query(models.Book).filter(
            public_review_filter(models.Book)
        ).limit(review_limit // 6).all()
        
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

        for review in music_reviews:
            sitemap_parts.append(f"""  <url>
    <loc>{base_url}/reviews/{review.id}?category=music</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")

        for review in book_reviews:
            sitemap_parts.append(f"""  <url>
    <loc>{base_url}/reviews/{review.id}?category=book</loc>
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
    site_url = os.getenv("SITE_URL", "https://omnitrackr.xyz")
    
    robots = f"""User-agent: Mediapartners-Google
Allow: /

User-agent: AdsBot-Google
Allow: /

User-agent: AdsBot-Google-Mobile
Allow: /

User-agent: *
Allow: /
Allow: /reviews
Allow: /about
Allow: /guides
Allow: /compare
Allow: /use-cases
Allow: /changelog
Allow: /tv-show-tracker
Allow: /game-tracker
Allow: /movie-tracker
Allow: /anime-tracker
Allow: /book-tracker
Allow: /music-tracker
Allow: /media-statistics
Allow: /export-import-guide
Allow: /demo
Allow: /media-tracking
Allow: /roadmap
Disallow: /auth/
Disallow: /api/
Disallow: /account/
Disallow: /notifications/
Disallow: /static/credentials.js

Sitemap: {site_url}/sitemap.xml
"""
    
    return Response(content=robots, media_type="text/plain")


@router.get("/ads.txt")
@router.head("/ads.txt")
async def get_ads_txt():
    publisher_id = os.getenv("ADSENSE_PUBLISHER_ID", "pub-7271682066779719")
    ads_txt = f"google.com, {publisher_id}, DIRECT, f08c47fec0942fa0\n"
    return Response(
        content=ads_txt,
        media_type="text/plain",
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Robots-Tag": "noindex",
        },
    )


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
- About: {base_url}/about
- Guides: {base_url}/guides
- Compare media trackers: {base_url}/compare
- Media tracking use cases: {base_url}/use-cases
- Changelog: {base_url}/changelog
- TV show tracker guide: {base_url}/tv-show-tracker
- Game tracker guide: {base_url}/game-tracker
- Movie tracker guide: {base_url}/movie-tracker
- Anime tracker guide: {base_url}/anime-tracker
- Book tracker guide: {base_url}/book-tracker
- Music tracker guide: {base_url}/music-tracker
- Media statistics guide: {base_url}/media-statistics
- Export and import guide: {base_url}/export-import-guide
- Demo library: {base_url}/demo
- Media tracking hub: {base_url}/media-tracking
- Roadmap: {base_url}/roadmap
- Terms: {base_url}/terms
- Contact: {base_url}/contact
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
- Music: Reviews and ratings for albums and artists
- Books: Reviews and ratings for books

## Public Content
Public reviews are available at {base_url}/reviews and individual review pages at {base_url}/reviews/[id]?category=[category]. OmniTrackr also publishes evergreen guidance at {base_url}/guides, {base_url}/media-tracking, {base_url}/compare, {base_url}/use-cases, {base_url}/movie-tracker, {base_url}/tv-show-tracker, {base_url}/anime-tracker, {base_url}/game-tracker, {base_url}/music-tracker, {base_url}/book-tracker, {base_url}/media-statistics, and {base_url}/export-import-guide, a sample library at {base_url}/demo, plus product updates at {base_url}/changelog and {base_url}/roadmap.

## Contact
Email: omnitrackr@gmail.com
Website: {base_url}
"""
    
    return Response(content=llms_content, media_type="text/plain")

