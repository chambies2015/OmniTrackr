"""
SEO endpoints for the OmniTrackr API.
"""
import os
import json
from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, func

from .. import models
from ..dependencies import get_db
from ..discover_guides import GUIDES
from ..review_quality import evaluate_public_review
from .collections import _approval_is_current, _media_lookup_for_collections
from .reviews import _current_state_hides_review

router = APIRouter(tags=["seo"])
PUBLIC_REVIEW_MIN_CHARS = int(os.getenv("PUBLIC_REVIEW_MIN_CHARS", "80"))
PUBLIC_REVIEW_DETAIL_MIN_CHARS = int(os.getenv("PUBLIC_REVIEW_DETAIL_MIN_CHARS", "240"))
REVIEW_CATEGORY_MODELS = (
    ("movie", models.Movie),
    ("tv_show", models.TVShow),
    ("anime", models.Anime),
    ("video_game", models.VideoGame),
    ("music", models.Music),
    ("book", models.Book),
)
# A sitemap is a recommendation, not an inventory dump. Supporting pages remain
# reachable through navigation, while this list concentrates crawling on the
# public experiences with a distinct purpose and a complete answer of their own.
CORE_SITEMAP_PATHS = (
    ("/", "weekly", "1.0"),
    ("/about", "monthly", "0.7"),
    ("/faq", "monthly", "0.7"),
    ("/guides", "monthly", "0.75"),
    ("/demo", "monthly", "0.8"),
    ("/media-tracking", "monthly", "0.85"),
    ("/export-import-guide", "monthly", "0.75"),
    ("/review-guidelines", "monthly", "0.75"),
    ("/sample-library", "monthly", "0.8"),
)


@router.get("/sitemap.xml")
async def get_sitemap(db: Session = Depends(get_db)):
    """Generate and serve sitemap.xml for SEO."""
    base_url = os.getenv("SITE_URL", "https://omnitrackr.xyz")
    today = datetime.now().strftime('%Y-%m-%d')
    sitemap_parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, changefreq, priority in CORE_SITEMAP_PATHS:
        sitemap_parts.append(
            f"  <url><loc>{base_url}{path}</loc><changefreq>{changefreq}</changefreq>"
            f"<priority>{priority}</priority></url>"
        )
    
    try:
        user_query = db.query(models.User.id).filter(models.User.is_active == True)
        public_detail_review_filter = lambda model_cls: and_(
            model_cls.review.isnot(None),
            model_cls.review != "",
            model_cls.review_public == True,
            func.length(func.trim(model_cls.review)) >= PUBLIC_REVIEW_DETAIL_MIN_CHARS,
            model_cls.user_id.in_(user_query)
        )

        def visible_search_ready(category, candidates):
            item_ids = [item.id for item in candidates]
            state_map = {
                state.item_id: state
                for state in db.query(models.PublicReviewState).filter(
                    models.PublicReviewState.category == category,
                    models.PublicReviewState.item_id.in_(item_ids),
                ).all()
            } if item_ids else {}
            return [
                item for item in candidates
                if (item.title or "").strip() and evaluate_public_review(
                    item.review, PUBLIC_REVIEW_MIN_CHARS, PUBLIC_REVIEW_DETAIL_MIN_CHARS
                ).search_ready
                and not _current_state_hides_review(state_map.get(item.id), category, item)
            ]

        review_directory_ready = False
        for category, model_cls in REVIEW_CATEGORY_MODELS:
            category_candidates = db.query(model_cls).filter(
                public_detail_review_filter(model_cls)
            ).limit(200).all()
            if visible_search_ready(category, category_candidates):
                review_directory_ready = True
                sitemap_parts.append(f"""  <url>
    <loc>{base_url}/reviews?category={category}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.72</priority>
  </url>""")
        
        review_limit = 600
        
        movie_reviews = db.query(models.Movie).filter(
            public_detail_review_filter(models.Movie)
        ).limit(review_limit // 6).all()
        movie_reviews = visible_search_ready("movie", movie_reviews)
        
        tv_reviews = db.query(models.TVShow).filter(
            public_detail_review_filter(models.TVShow)
        ).limit(review_limit // 6).all()
        tv_reviews = visible_search_ready("tv_show", tv_reviews)
        
        anime_reviews = db.query(models.Anime).filter(
            public_detail_review_filter(models.Anime)
        ).limit(review_limit // 6).all()
        anime_reviews = visible_search_ready("anime", anime_reviews)
        
        vg_reviews = db.query(models.VideoGame).filter(
            public_detail_review_filter(models.VideoGame)
        ).limit(review_limit // 6).all()
        vg_reviews = visible_search_ready("video_game", vg_reviews)

        music_reviews = db.query(models.Music).filter(
            public_detail_review_filter(models.Music)
        ).limit(review_limit // 6).all()
        music_reviews = visible_search_ready("music", music_reviews)

        book_reviews = db.query(models.Book).filter(
            public_detail_review_filter(models.Book)
        ).limit(review_limit // 6).all()
        book_reviews = visible_search_ready("book", book_reviews)
        
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

        if review_directory_ready:
            sitemap_parts.append(
                f"  <url><loc>{base_url}/reviews</loc><changefreq>daily</changefreq>"
                "<priority>0.8</priority></url>"
            )

        approved_collections = db.query(models.Collection).options(selectinload(models.Collection.items)).join(
            models.User, models.Collection.user_id == models.User.id
        ).filter(
            models.Collection.is_public == True,
            models.Collection.moderation_status != "rejected",
            models.User.is_active == True,
            func.length(func.trim(models.Collection.description)) >= 300,
        ).order_by(models.Collection.published_at.desc()).limit(500).all()
        collection_media = _media_lookup_for_collections(db, approved_collections)
        eligible_collection_count = 0
        for collection in approved_collections:
            if not _approval_is_current(collection, db, collection_media):
                continue
            available_count = sum(
                1 for item in collection.items
                if (collection.user_id, item.category, item.item_id) in collection_media
            )
            if available_count >= 3:
                eligible_collection_count += 1
                sitemap_parts.append(
                    f"  <url><loc>{base_url}/collections/public/{collection.id}</loc>"
                    f"<lastmod>{today}</lastmod><changefreq>monthly</changefreq><priority>0.65</priority></url>"
                )
        if eligible_collection_count >= 3:
            sitemap_parts.append(
                f"  <url><loc>{base_url}/collections/explore</loc><changefreq>daily</changefreq><priority>0.8</priority></url>"
            )
    except Exception:
        pass
    
    from ..discover_catalog import MONTHLY_EDITIONS
    for path in [
        "/discover",
        *[f"/discover/monthly/{slug}" for slug in MONTHLY_EDITIONS],
    ]:
        sitemap_parts.append(f"<url><loc>{base_url}{path}</loc></url>")
    # Only the completed editorial guides join the search inventory. Shorter
    # trails remain available to readers without being submitted for indexing.
    for slug, guide in GUIDES.items():
        sitemap_parts.append(
            f"<url><loc>{base_url}/discover/{slug}</loc>"
            f"<lastmod>{guide['reviewed']}</lastmod>"
            "<changefreq>monthly</changefreq><priority>0.75</priority></url>"
        )
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
Allow: /ads.txt
Allow: /sellers.json
Disallow: /auth/
Disallow: /api/
Disallow: /account/
Disallow: /friends
Disallow: /movies/
Disallow: /tv-shows/
Disallow: /anime/
Disallow: /video-games/
Disallow: /music/
Disallow: /books/
Disallow: /statistics/
Disallow: /custom-tabs/
Disallow: /export/
Disallow: /import/
Disallow: /notifications/
Disallow: /profile-pictures/
Disallow: /custom-tab-posters/
Disallow: /static/profile_pictures/
Disallow: /docs
Disallow: /redoc
Disallow: /openapi.json
Disallow: /credentials.js
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
        media_type="application/json",
        headers={"X-Robots-Tag": "noindex"},
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
- FAQ: {base_url}/faq
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
- Media tracker setup checklist: {base_url}/media-tracker-checklist
- Media tracking templates: {base_url}/tracking-templates
- Media review guidelines: {base_url}/review-guidelines
- Sample library: {base_url}/sample-library
- Demo library: {base_url}/demo
- Media tracking hub: {base_url}/media-tracking
- Roadmap: {base_url}/roadmap
- Terms: {base_url}/terms
- Contact: {base_url}/contact
- Privacy Policy: {base_url}/privacy
- Advertising Policy: {base_url}/advertising
- Content Quality Policy: {base_url}/content-quality
- HTML Site Map: {base_url}/site-map
- Public Reviews: {base_url}/reviews
- Community Collections: {base_url}/collections/explore

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
Public reviews are available at {base_url}/reviews and individual review pages at {base_url}/reviews/[id]?category=[category]. OmniTrackr also publishes evergreen guidance at {base_url}/faq, {base_url}/guides, {base_url}/media-tracking, {base_url}/compare, {base_url}/use-cases, {base_url}/movie-tracker, {base_url}/tv-show-tracker, {base_url}/anime-tracker, {base_url}/game-tracker, {base_url}/music-tracker, {base_url}/book-tracker, {base_url}/media-statistics, {base_url}/export-import-guide, {base_url}/media-tracker-checklist, {base_url}/tracking-templates, and {base_url}/review-guidelines, a demo library at {base_url}/demo, a sample media library at {base_url}/sample-library, a human-readable site map at {base_url}/site-map, product updates at {base_url}/changelog and {base_url}/roadmap, ad transparency at {base_url}/advertising, and content quality standards at {base_url}/content-quality.
Automatically qualified member collections are browsable at {base_url}/collections/explore. Share-ready collections that miss the stricter discovery checks remain available only by direct link and stay outside the search index. Version-bound reports can temporarily unlist a collection without deleting it.

## Quality and Advertising Boundaries
- Public ad-eligible pages are intended to be original, useful, and readable before signup.
- The private authenticated app shell, account settings, editing forms, import/export controls, password flows, and private user libraries are not ad placement surfaces.
- Public review directory pages default to substantial opt-in reviews; standalone review detail pages require longer review text before they are indexed, added to the sitemap, or treated as ad-eligible.
- Empty API documentation, private account routes, generated docs, and utility endpoints are kept out of public search inventory.
- Advertising, content quality, privacy, and site-map pages explain how OmniTrackr separates public informational content from private account data.

## Contact
Email: omnitrackr@gmail.com
Website: {base_url}
"""
    
    return Response(
        content=llms_content,
        media_type="text/plain",
        headers={"X-Robots-Tag": "noindex"},
    )

