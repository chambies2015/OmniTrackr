"""
SEO endpoints for the OmniTrackr API.
"""
import os
import json
import threading
import time
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, func

from .. import models, release_radar
from ..dependencies import get_db
from ..discover_guides import GUIDES
from ..review_quality import AD_MIN_REVIEW_WORDS, MIN_INDEXED_LISTING_REVIEWS, evaluate_public_review, word_count
from .collections import _approval_is_current, _media_lookup_for_collections
from .reviews import _current_state_hides_review

router = APIRouter(tags=["seo"])
SITEMAP_CACHE_SECONDS = 15 * 60
_sitemap_cache = {"at": 0.0, "parts": None, "refreshing": False}
_sitemap_lock = threading.Lock()


def _sitemap_cache_enabled() -> bool:
    # Tests change data between requests and expect the sitemap to follow at once.
    return os.getenv("TESTING", "").lower() != "true"


PUBLIC_REVIEW_MIN_CHARS = int(os.getenv("PUBLIC_REVIEW_MIN_CHARS", "80"))
PUBLIC_REVIEW_DETAIL_MIN_CHARS = int(os.getenv("PUBLIC_REVIEW_DETAIL_MIN_CHARS", "240"))
REVIEW_CATEGORY_MODELS = (
    ("movie", models.Movie),
    ("tv_show", models.TVShow),
    ("anime", models.Anime),
    ("video_game", models.VideoGame),
    ("music", models.Music),
    ("book", models.Book),
    ("manga", models.Manga),
    ("podcast", models.Podcast),
    ("audiobook", models.Audiobook),
)
# A sitemap is a recommendation, not an inventory dump. Supporting pages remain
# reachable through navigation, while this list concentrates crawling on the
# public experiences with a distinct purpose and a complete answer of their own.
CORE_SITEMAP_PATHS = (
    ("/", "weekly", "1.0"),
    ("/about", "monthly", "0.7"),
    ("/faq", "monthly", "0.7"),
    ("/guides", "monthly", "0.75"),
    ("/compare", "monthly", "0.7"),
    ("/demo", "monthly", "0.8"),
    ("/media-tracking", "monthly", "0.85"),
    ("/export-import-guide", "monthly", "0.75"),
    ("/switch", "monthly", "0.75"),
    ("/review-guidelines", "monthly", "0.75"),
    ("/sample-library", "monthly", "0.8"),
    ("/pick", "weekly", "0.7"),
    ("/tonight", "monthly", "0.6"),
    ("/tier-list", "monthly", "0.7"),
    ("/binge-calculator", "monthly", "0.7"),
    ("/if-you-liked", "monthly", "0.75"),
    ("/best-of", "weekly", "0.75"),
    ("/in-order", "monthly", "0.75"),
    ("/halloween", "weekly", "0.75"),
    ("/holidays", "weekly", "0.75"),
    ("/daily", "daily", "0.8"),
    ("/movie-tracker", "monthly", "0.75"),
    ("/tv-show-tracker", "monthly", "0.75"),
    ("/anime-tracker", "monthly", "0.75"),
    ("/game-tracker", "monthly", "0.75"),
    ("/book-tracker", "monthly", "0.75"),
    ("/manga-tracker", "monthly", "0.75"),
    ("/podcast-tracker", "monthly", "0.75"),
    ("/audiobook-tracker", "monthly", "0.75"),
    ("/music-tracker", "monthly", "0.75"),
    ("/use-cases", "monthly", "0.7"),
)


def _database_parts(db: Session) -> list[str]:
    """Sitemap entries that come from member data: reviews, collections, guides, title pages, profiles."""
    base_url = os.getenv("SITE_URL", "https://omnitrackr.xyz")
    today = datetime.now().strftime('%Y-%m-%d')
    sitemap_parts = []
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

        def page_worthy(items):
            # Review pages are listed only when the review carries the page alone (see reviews._review_is_indexable).
            return [item for item in items if word_count(item.review) >= AD_MIN_REVIEW_WORDS]

        search_ready_total = 0
        for category, model_cls in REVIEW_CATEGORY_MODELS:
            category_candidates = db.query(model_cls).filter(
                public_detail_review_filter(model_cls)
            ).limit(200).all()
            ready_count = len(visible_search_ready(category, category_candidates))
            search_ready_total += ready_count
            if ready_count >= MIN_INDEXED_LISTING_REVIEWS:
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
        movie_reviews = page_worthy(visible_search_ready("movie", movie_reviews))
        
        tv_reviews = db.query(models.TVShow).filter(
            public_detail_review_filter(models.TVShow)
        ).limit(review_limit // 6).all()
        tv_reviews = page_worthy(visible_search_ready("tv_show", tv_reviews))
        
        anime_reviews = db.query(models.Anime).filter(
            public_detail_review_filter(models.Anime)
        ).limit(review_limit // 6).all()
        anime_reviews = page_worthy(visible_search_ready("anime", anime_reviews))
        
        vg_reviews = db.query(models.VideoGame).filter(
            public_detail_review_filter(models.VideoGame)
        ).limit(review_limit // 6).all()
        vg_reviews = page_worthy(visible_search_ready("video_game", vg_reviews))

        music_reviews = db.query(models.Music).filter(
            public_detail_review_filter(models.Music)
        ).limit(review_limit // 6).all()
        music_reviews = page_worthy(visible_search_ready("music", music_reviews))

        book_reviews = db.query(models.Book).filter(
            public_detail_review_filter(models.Book)
        ).limit(review_limit // 6).all()
        book_reviews = page_worthy(visible_search_ready("book", book_reviews))

        manga_reviews = db.query(models.Manga).filter(
            public_detail_review_filter(models.Manga)
        ).limit(review_limit // 6).all()
        manga_reviews = page_worthy(visible_search_ready("manga", manga_reviews))

        podcast_reviews = db.query(models.Podcast).filter(
            public_detail_review_filter(models.Podcast)
        ).limit(review_limit // 6).all()
        podcast_reviews = page_worthy(visible_search_ready("podcast", podcast_reviews))

        audiobook_reviews = db.query(models.Audiobook).filter(
            public_detail_review_filter(models.Audiobook)
        ).limit(review_limit // 6).all()
        audiobook_reviews = page_worthy(visible_search_ready("audiobook", audiobook_reviews))
        
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

        for review in manga_reviews:
            sitemap_parts.append(f"""  <url>
    <loc>{base_url}/reviews/{review.id}?category=manga</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")

        for review in podcast_reviews:
            sitemap_parts.append(f"""  <url>
    <loc>{base_url}/reviews/{review.id}?category=podcast</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")

        for review in audiobook_reviews:
            sitemap_parts.append(f"""  <url>
    <loc>{base_url}/reviews/{review.id}?category=audiobook</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>""")

        if search_ready_total >= MIN_INDEXED_LISTING_REVIEWS:
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
    
    from ..discover_catalog import published_editions
    sitemap_parts.append(f"<url><loc>{base_url}/discover</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>")
    # Browse shelves: written pages with a live chart on top (see app/browse.py).
    from .. import browse
    sitemap_parts.append(f"<url><loc>{base_url}{browse.path()}</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>")
    for browse_kind in browse.KINDS:
        sitemap_parts.append(f"<url><loc>{base_url}{browse.path(browse_kind)}</loc><changefreq>daily</changefreq><priority>0.8</priority></url>")
    for slug, edition in published_editions().items():
        sitemap_parts.append(
            f"<url><loc>{base_url}/discover/monthly/{slug}</loc>"
            f"<lastmod>{edition['published_date']}</lastmod>"
            "<changefreq>monthly</changefreq><priority>0.75</priority></url>"
        )
    # Monthly challenge guides that have started; future months stay unpublished.
    from .. import challenges
    challenge_months = challenges.public_months()
    if challenge_months:
        sitemap_parts.append(f"<url><loc>{base_url}/challenges</loc><changefreq>monthly</changefreq><priority>0.7</priority></url>")
    for month in challenge_months:
        sitemap_parts.append(
            f"<url><loc>{base_url}/challenges/{challenges.slug_for(month)}</loc>"
            f"<lastmod>{challenges.CHALLENGES[month]['published']}</lastmod>"
            "<changefreq>monthly</changefreq><priority>0.7</priority></url>"
        )
    # OmniTrackr Daily: the archive and each finished puzzle (today's answer stays off the sitemap).
    from .. import daily
    daily_numbers = daily.archive_numbers()
    if daily_numbers:
        sitemap_parts.append(f"<url><loc>{base_url}/daily/archive</loc><changefreq>daily</changefreq><priority>0.6</priority></url>")
    for number in daily_numbers:
        sitemap_parts.append(
            f"<url><loc>{base_url}/daily/{number}</loc><lastmod>{daily.date_for(number).isoformat()}</lastmod>"
            "<changefreq>yearly</changefreq><priority>0.5</priority></url>"
        )
    # Only the completed editorial guides join the search inventory. Shorter
    # trails remain available to readers without being submitted for indexing.
    for slug, guide in GUIDES.items():
        sitemap_parts.append(
            f"<url><loc>{base_url}/discover/{slug}</loc>"
            f"<lastmod>{guide['reviewed']}</lastmod>"
            "<changefreq>monthly</changefreq><priority>0.75</priority></url>"
        )
    # "If you liked" guides: hand-written, complete pages.
    from .. import if_you_liked
    from ..if_you_liked_guides import GUIDES as LIKED_GUIDES
    for slug, guide in LIKED_GUIDES.items():
        sitemap_parts.append(
            f"<url><loc>{base_url}{if_you_liked.path(slug)}</loc>"
            f"<lastmod>{guide['reviewed']}</lastmod>"
            "<changefreq>monthly</changefreq><priority>0.75</priority></url>"
        )
    # Best-of-the-year lists: hand-written, complete pages, updated through the year.
    from .. import best_of
    from ..best_of_guides import GUIDES as BEST_OF_GUIDES
    for slug, guide in BEST_OF_GUIDES.items():
        sitemap_parts.append(
            f"<url><loc>{base_url}{best_of.path(slug)}</loc>"
            f"<lastmod>{guide['reviewed']}</lastmod>"
            "<changefreq>weekly</changefreq><priority>0.75</priority></url>"
        )
    # Release guides: hand-written picks from a month's (or a season's) new releases, live from their publish date.
    from .. import new_releases
    release_guides = new_releases.published()
    if release_guides:
        sitemap_parts.append(f"<url><loc>{base_url}{new_releases.BASE_PATH}</loc><changefreq>weekly</changefreq><priority>0.75</priority></url>")
    for slug, guide in release_guides.items():
        sitemap_parts.append(
            f"<url><loc>{base_url}{new_releases.path(slug)}</loc>"
            f"<lastmod>{guide['reviewed']}</lastmod>"
            "<changefreq>weekly</changefreq><priority>0.75</priority></url>"
        )
    # "Switch from X" guides: one hand-written page per service the Import Studio reads.
    from .. import switch_guides
    for slug, guide in switch_guides.GUIDES.items():
        sitemap_parts.append(
            f"<url><loc>{base_url}{switch_guides.path(slug)}</loc>"
            f"<lastmod>{guide['reviewed']}</lastmod>"
            "<changefreq>monthly</changefreq><priority>0.7</priority></url>"
        )
    # "In order" guides: hand-written, complete pages.
    from .. import in_order
    from ..in_order_guides import GUIDES as ORDER_GUIDES
    for slug, guide in ORDER_GUIDES.items():
        sitemap_parts.append(
            f"<url><loc>{base_url}{in_order.path(slug)}</loc>"
            f"<lastmod>{guide['reviewed']}</lastmod>"
            "<changefreq>monthly</changefreq><priority>0.75</priority></url>"
        )
    # Title pages join only when they have real substance (see title_pages.is_indexable).
    try:
        from .titles import sitemap_entries
        from .. import title_pages
        title_paths = sitemap_entries(db)
        if len(title_pages.reviewed_titles(db)) >= 8:
            sitemap_parts.append(f"<url><loc>{base_url}/titles</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>")
        for path in title_paths:
            sitemap_parts.append(f"<url><loc>{base_url}{path}</loc><changefreq>weekly</changefreq><priority>0.65</priority></url>")
        # Member charts join once enough titles have member ratings to rank (see title_charts).
        from .. import title_charts
        for path in title_charts.indexable_paths(db):
            sitemap_parts.append(f"<url><loc>{base_url}{path}</loc><changefreq>daily</changefreq><priority>0.7</priority></url>")
    except Exception:
        pass
    # Trending pages join once enough titles are named for the period (see trending.indexable_paths).
    try:
        from .. import trending
        for path in trending.indexable_paths(db):
            sitemap_parts.append(f"<url><loc>{base_url}{path}</loc><changefreq>daily</changefreq><priority>0.7</priority></url>")
    except Exception:
        db.rollback()
    # People and studio pages join once members have rated and reviewed enough of the work (people_pages.is_indexable).
    try:
        from .. import people_pages
        from .people import directory_is_indexable
        for entity, directory_path in (("person", "/people"), ("studio", "/studios")):
            if directory_is_indexable(db, entity):
                sitemap_parts.append(f"<url><loc>{base_url}{directory_path}</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>")
        for path in people_pages.sitemap_paths(db):
            sitemap_parts.append(f"<url><loc>{base_url}{path}</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>")
    except Exception:
        db.rollback()
    # Title discussions join once a thread carries as much member writing as an indexed review.
    try:
        from .. import title_discussions
        for path, active in title_discussions.sitemap_paths(db):
            sitemap_parts.append(f"<url><loc>{base_url}{path}</loc><lastmod>{active.date().isoformat()}</lastmod>"
                                 "<changefreq>weekly</changefreq><priority>0.5</priority></url>")
    except Exception:
        db.rollback()
    # Weekly roundups join once a week has enough releases and write-up (see weekly_roundup.is_indexable).
    try:
        from .. import weekly_roundup
        roundup_weeks = [(monday, payload, final) for monday, payload, final in weekly_roundup.weeks(db)
                         if weekly_roundup.is_indexable(payload, monday)]
        if roundup_weeks:
            sitemap_parts.append(f"<url><loc>{base_url}{weekly_roundup.ARCHIVE_PATH}</loc><lastmod>{roundup_weeks[0][0].isoformat()}</lastmod>"
                                 "<changefreq>weekly</changefreq><priority>0.7</priority></url>")
        for monday, payload, final in roundup_weeks:
            lastmod = max((payload.get("built_at") or "")[:10], monday.isoformat())
            sitemap_parts.append(f"<url><loc>{base_url}{weekly_roundup.path(monday)}</loc><lastmod>{lastmod}</lastmod>"
                                 f"<changefreq>{'yearly' if final else 'daily'}</changefreq><priority>{'0.55' if final else '0.75'}</priority></url>")
    except Exception:
        db.rollback()
    # Public profiles join only when the member opted in and the page has original content.
    try:
        from .. import public_profiles
        for path in public_profiles.sitemap_paths(db):
            sitemap_parts.append(f"<url><loc>{base_url}{path}</loc><changefreq>weekly</changefreq><priority>0.4</priority></url>")
    except Exception:
        pass
    return sitemap_parts


def _refresh_database_parts() -> None:
    """Rebuild the member-data entries on a worker thread with its own session."""
    from ..database import SessionLocal

    def run():
        db = SessionLocal()
        try:
            parts = _database_parts(db)
            with _sitemap_lock:
                _sitemap_cache["parts"] = parts
                _sitemap_cache["at"] = time.monotonic()
        except Exception as error:
            print(f"Sitemap refresh failed: {error}")
        finally:
            db.close()
            with _sitemap_lock:
                _sitemap_cache["refreshing"] = False

    threading.Thread(target=run, name="sitemap-refresh", daemon=True).start()


def _cached_database_parts(db: Session) -> list[str]:
    """The member-data entries, rebuilt at most every SITEMAP_CACHE_SECONDS.

    Building them reads every public review and checks hundreds of title pages (half a
    minute on a large library), and crawlers fetch the sitemap often. Only the first
    request after a restart waits for a build. After that an expired copy is still
    served while one rebuild runs on a worker thread, so a crawler never sits through it.
    """
    if not _sitemap_cache_enabled():
        return _database_parts(db)
    with _sitemap_lock:
        if _sitemap_cache["parts"] is None:
            _sitemap_cache["parts"] = _database_parts(db)
            _sitemap_cache["at"] = time.monotonic()
        elif (time.monotonic() - _sitemap_cache["at"] >= SITEMAP_CACHE_SECONDS
              and not _sitemap_cache["refreshing"]):
            _sitemap_cache["refreshing"] = True
            _refresh_database_parts()
        return _sitemap_cache["parts"]


@router.get("/sitemap.xml")
async def get_sitemap(request: Request = None, db: Session = Depends(get_db)):
    """Generate and serve sitemap.xml for SEO."""
    base_url = os.getenv("SITE_URL", "https://omnitrackr.xyz")
    today = datetime.now().strftime('%Y-%m-%d')
    sitemap_parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, changefreq, priority in CORE_SITEMAP_PATHS:
        sitemap_parts.append(
            f"  <url><loc>{base_url}{path}</loc><changefreq>{changefreq}</changefreq>"
            f"<priority>{priority}</priority></url>"
        )
    
    # Release Radar pages are listed only when their cached data makes them
    # indexable (a cold cache is warmed in the background for the next crawl).
    radar_client = getattr(request.app.state, "external_api_client", None) if request else None
    featured_total = 0
    radar_parts = []
    for radar_category in release_radar.CATEGORY_ORDER:
        featured = release_radar.featured_window(radar_category)
        for window in release_radar.allowed_windows(radar_category):
            if window.start < featured.start:
                continue
            cached = release_radar.CACHE.peek(window)
            count = len(cached.get("items", [])) if cached else 0
            if window == featured:
                featured_total += count
                if cached is None and radar_client is not None:
                    release_radar.CACHE.warm(radar_client, window)
            if count >= release_radar.MIN_INDEXABLE_ITEMS and release_radar.INDEX_CATEGORY_PAGES:
                path = f"/release-radar/{radar_category}" if window == featured else f"/release-radar/{radar_category}/{window.slug}"
                changefreq, priority = ("daily", "0.8") if window == featured else ("weekly", "0.6")
                radar_parts.append(
                    f"  <url><loc>{base_url}{path}</loc><lastmod>{today}</lastmod>"
                    f"<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>"
                )
    if featured_total >= release_radar.MIN_INDEXABLE_ITEMS:
        sitemap_parts.append(f"  <url><loc>{base_url}/release-radar</loc><lastmod>{today}</lastmod><changefreq>daily</changefreq><priority>0.85</priority></url>")
    sitemap_parts.extend(radar_parts)

    # Off the event loop: building these entries reads the database for seconds on a cold cache.
    sitemap_parts.extend(await run_in_threadpool(_cached_database_parts, db))
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
Disallow: /manga/
Disallow: /podcasts/
Disallow: /audiobooks/
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
OmniTrackr is a free web application for tracking and organizing movies, TV shows, anime, video games, music, books, manga, podcasts, and audiobooks. Users can rate, review, and analyze their media collection with comprehensive statistics, beautiful posters and cover art, and social features.

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
- Manga tracker guide: {base_url}/manga-tracker
- Podcast tracker guide: {base_url}/podcast-tracker
- Audiobook tracker guide: {base_url}/audiobook-tracker
- Music tracker guide: {base_url}/music-tracker
- Media statistics guide: {base_url}/media-statistics
- Export and import guide: {base_url}/export-import-guide
- Switching guide (Letterboxd, IMDb, Goodreads, StoryGraph, MyAnimeList, Kitsu, AniList, Trakt, Steam, Spotify, podcast apps, Rate Your Music, Libib): {base_url}/switch, with one page per service such as {base_url}/switch/letterboxd and {base_url}/switch/spotify
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
- Editorial Standards: {base_url}/content-quality
- HTML Site Map: {base_url}/site-map
- Public Reviews: {base_url}/reviews
- Community Collections: {base_url}/collections/explore

## Features
- Track movies, TV shows, anime, video games, music, books, manga, podcasts, and audiobooks
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
- Manga: Reviews and ratings for manga, manhwa and manhua
- Podcasts: Reviews and ratings for podcast shows
- Audiobooks: Reviews and ratings for audiobooks, including the narrator

## Public Content
Public reviews are available at {base_url}/reviews and individual review pages at {base_url}/reviews/[id]?category=[category]. OmniTrackr also publishes evergreen guidance at {base_url}/faq, {base_url}/guides, {base_url}/media-tracking, {base_url}/compare, {base_url}/use-cases, {base_url}/movie-tracker, {base_url}/tv-show-tracker, {base_url}/anime-tracker, {base_url}/game-tracker, {base_url}/music-tracker, {base_url}/book-tracker, {base_url}/media-statistics, {base_url}/export-import-guide, {base_url}/media-tracker-checklist, {base_url}/tracking-templates, and {base_url}/review-guidelines, a demo library at {base_url}/demo, a sample media library at {base_url}/sample-library, a human-readable site map at {base_url}/site-map, product updates at {base_url}/changelog and {base_url}/roadmap, ad transparency at {base_url}/advertising, and editorial standards at {base_url}/content-quality.
Release Radar at {base_url}/release-radar lists upcoming movies (Wikidata), TV premieres (TVmaze), the current anime season (AniList), and new video games (RAWG), refreshed every few hours, with one-click tracking for members.
"If you liked" guides at {base_url}/if-you-liked recommend what to watch, play, read or hear after a well-loved title (for example {base_url}/if-you-liked/interstellar), across formats, with why each pick fits and a caveat.
Seasonal picks at {base_url}/halloween sort horror and spooky movies, shows, anime, games, books and music by fright level, from family-friendly to properly frightening, with a caveat for each. Holiday picks at {base_url}/holidays cover Thanksgiving, Christmas and winter in the same six formats, sorted by festive level, from snowy stories with no holiday at all to full tinsel.
"In order" guides at {base_url}/in-order give the best order to watch, read and play a franchise (for example {base_url}/in-order/star-wars), with release order, story order, what each entry adds and what is optional.
Weekly release roundups at {base_url}/new-this-week (archive at {base_url}/new-this-week/archive) list each week's new movies, TV premieres, anime and games from Release Radar, with a short write-up calculated from that data and anonymous totals of what OmniTrackr members finished that week. Past weeks are kept unchanged.
Trending charts at {base_url}/trending (and {base_url}/trending/month, plus one per format such as {base_url}/trending/movie) rank the titles OmniTrackr members added, started and finished most in the last 7 or 30 days, compared with the period before. They use anonymous totals only and name a title once at least two members picked it up.

Best-of-the-year lists at {base_url}/best-of pick the best new movies, TV shows, anime, games and books of each year (for example {base_url}/best-of/2026/movies), with release details, why each pick made the list, a caveat and the sources checked.
Pick for me at {base_url}/pick suggests one editorially chosen movie, TV show, anime, game, book or album at a time, with the reason it was chosen and a caveat.
OmniTrackr Daily at {base_url}/daily is a free daily guessing game: one movie, TV show, anime, game, book or album a day, guessed from six clues, with past puzzles, answers and editors' notes at {base_url}/daily/archive.
The tier list maker at {base_url}/tier-list ranks movies, TV shows, anime, games, books or albums from S to D in the browser and saves the board as an image; boards are never stored on the server.
The binge calculator at {base_url}/binge-calculator works out how many hours a TV show, anime or book series takes and the finish date at a chosen pace, with worked examples for long series.

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

