"""
Entry point for the OmniTrackr API.
Provides CRUD endpoints for managing movies and TV shows.
"""
import asyncio
import os
import re
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from . import crud, schemas, models, dashboard_assets
from .database import Base, SessionLocal, engine
from .site_chrome import apply_site_chrome, message_page
from .csp import nonce_html_response, strict_html_response
from .auth import AUTH_COOKIE_NAME
from .migrations import run_migrations
from .middleware import SecurityHeadersMiddleware, BotFilterMiddleware
from .site_traffic import RECORDER as TRAFFIC_RECORDER, SiteTrafficMiddleware
from . import digest as digest_emails
from . import funnel
from .dependencies import get_db, get_current_user
from .routers import (
    auth,
    account,
    friends,
    notifications,
    movies,
    tv_shows,
    anime,
    video_games,
    music,
    books,
    statistics,
    export_import,
    proxy,
    seo,
    static,
    custom_tabs,
    reviews,
    next_up,
    completion_moments,
    activity,
    progress,
    collections,
    discover,
    release_radar,
    import_studio,
    recommendations,
    site_stats,
    for_you,
    titles,
    profiles,
    pwa,
    supporters,
    year_in_review,
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Run migrations
run_migrations()

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Own pooled network resources and lightweight startup maintenance."""
    application.state.external_api_client = httpx.AsyncClient(
        timeout=httpx.Timeout(12.0, connect=5.0),
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        follow_redirects=False,
    )
    try:
        db = SessionLocal()
        try:
            expired_count = crud.expire_friend_requests(db)
            if expired_count > 0:
                print(f"Expired {expired_count} old friend requests on startup")
        finally:
            db.close()
    except Exception as e:
        print(f"Error expiring friend requests on startup: {e}")

    digest_task = None
    title_task = None
    announcement_task = None
    if digest_emails.enabled_for_process():
        digest_task = asyncio.create_task(digest_emails.digest_loop(application))
    from . import announcements
    if announcements.enabled_for_process():
        announcement_task = asyncio.create_task(announcements.announcement_loop(application))
    if os.getenv("TESTING", "").lower() != "true":
        title_task = asyncio.create_task(titles.warm_loop(application))
    try:
        yield
    finally:
        for task in (digest_task, title_task, announcement_task):
            if task is not None:
                task.cancel()
        await application.state.external_api_client.aclose()
        try:
            TRAFFIC_RECORDER.flush()  # Keep the last minute of page-view counts.
        except Exception:
            pass


# Initialize FastAPI
app = FastAPI(
    title="OmniTrackr API",
    description="Manage your movies, TV shows, anime, video games, music, and books",
    version="0.1.0",
    lifespan=lifespan,
)

def client_address(request: Request) -> str:
    """The visitor's address for rate limits.

    On Render every request reaches the app from an internal load balancer, so
    limits keyed on the socket address were shared by all visitors (for example
    five sign-ups a minute for the whole site). Render sits behind Cloudflare,
    which sets True-Client-IP / CF-Connecting-IP to the real visitor and
    overwrites any value a client sends. Those headers are trusted only when
    running on Render (RENDER=true, set by Render itself).
    """
    if os.getenv("RENDER", "").lower() == "true":
        for header in ("true-client-ip", "cf-connecting-ip"):
            value = (request.headers.get(header) or "").strip()
            if value:
                return value[:64]
    return get_remote_address(request)


# Initialize rate limiter
if os.getenv("TESTING", "").lower() == "true":
    limiter = Limiter(key_func=lambda: "test", enabled=False)
else:
    limiter = Limiter(key_func=client_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


HTML_404_EXCLUDED_PREFIXES = ("/api/", "/auth/", "/static/", "/docs", "/redoc", "/openapi.json")


async def friendly_not_found(request: Request, exc: StarletteHTTPException):
    """Browsers get a styled 404 page for public URLs; API clients keep JSON errors."""
    wants_html = "text/html" in request.headers.get("accept", "")
    if (exc.status_code == 404 and wants_html and request.method in ("GET", "HEAD")
            and not request.url.path.startswith(HTML_404_EXCLUDED_PREFIXES)):
        page = message_page(
            "Page not found", "This page drifted into the void",
            "The link may be old or mistyped. One of these should get you back on track.",
            eyebrow="404",
            actions=(("Go to the homepage", "/"), ("See what's coming out", "/release-radar"), ("Browse reviews", "/reviews")),
        )
        return strict_html_response(page, status_code=404)
    return await http_exception_handler(request, exc)


app.add_exception_handler(StarletteHTTPException, friendly_not_found)


def bind_rate_limited_endpoint(route, endpoint) -> None:
    """Replace both the visible endpoint and FastAPI's captured request callable."""
    route.endpoint = endpoint
    if hasattr(route, "dependant"):
        route.dependant.call = endpoint


# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BotFilterMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SiteTrafficMiddleware)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# Trust pages (privacy, terms, contact) stay indexable so search and ad
# reviewers see the same site identity a visitor does; they are still left out
# of the sitemap. The source-checked comparison is original reference content.
INDEXABLE_PUBLIC_TEMPLATES = {
    "about.html",
    "compare.html",
    "contact.html",
    "demo.html",
    "export_import_guide.html",
    "faq.html",
    "guides.html",
    "media_tracking.html",
    "review_guidelines.html",
    "sample_library.html",
    "privacy.html",
    "reviews.html",
    "terms.html",
}

# Ads are limited to the small set of pages that provide a complete experience
# without an account.  Directory, policy, release-note, and overlapping guide
# pages remain useful and linked, but are not treated as advertising inventory.
AD_ELIGIBLE_TEMPLATES = {
    "export_import_guide.html",
    "media_tracking.html",
    "review_guidelines.html",
    "sample_library.html",
}

NOFOLLOW_PUBLIC_TEMPLATES = {"recommendation_postcard.html"}


def inject_adsense_account_meta(html: str) -> str:
    publisher_id = os.getenv("ADSENSE_PUBLISHER_ID", "pub-7271682066779719")
    account = publisher_id if publisher_id.startswith("ca-") else f"ca-{publisher_id}"
    if "google-adsense-account" in html or "</head>" not in html:
        return html
    meta = f'  <meta name="google-adsense-account" content="{account}">\n'
    return html.replace("</head>", f"{meta}</head>", 1)


def inject_public_ad_loader(html: str, template_name: str, request: Request | None = None) -> str:
    if template_name not in AD_ELIGIBLE_TEMPLATES:
        return html
    if request and request.cookies.get(AUTH_COOKIE_NAME):
        return html
    if "/static/ad-loader.js" in html or "</head>" not in html:
        return html
    loader = '  <script src="/static/ad-loader.js" defer></script>\n'
    return html.replace("</head>", f"{loader}</head>", 1)


def apply_public_search_policy(html: str, template_name: str) -> tuple[str, bool]:
    """Keep useful supporting pages accessible without diluting search inventory."""
    indexable = template_name in INDEXABLE_PUBLIC_TEMPLATES
    if indexable:
        return html, True

    directive = "noindex, nofollow" if template_name in NOFOLLOW_PUBLIC_TEMPLATES else "noindex, follow"
    noindex_meta = f'<meta name="robots" content="{directive}">'
    robots_pattern = r'<meta\s+name=["\']robots["\']\s+content=["\'][^"\']*["\']\s*/?>'
    if re.search(robots_pattern, html, flags=re.IGNORECASE):
        html = re.sub(robots_pattern, noindex_meta, html, count=1, flags=re.IGNORECASE)
    elif "</head>" in html:
        html = html.replace("</head>", f"  {noindex_meta}\n</head>", 1)
    return html, False


def strict_template_response(template_name: str, request: Request | None = None):
    html_file = os.path.join(os.path.dirname(__file__), "templates", template_name)
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as file:
            html, indexable = apply_public_search_policy(apply_site_chrome(file.read()), template_name)
            html = inject_adsense_account_meta(html)
            response = strict_html_response(inject_public_ad_loader(html, template_name, request))
            response.headers["Vary"] = "Cookie"
            if not indexable:
                response.headers["X-Robots-Tag"] = (
                    "noindex, nofollow" if template_name in NOFOLLOW_PUBLIC_TEMPLATES else "noindex, follow"
                )
            return response
    return None


def public_root_html(html: str, request: Request | None = None) -> str:
    """Return the standalone public landing experience without the private app shell.

    The dashboard and its empty tables used to be sent to every anonymous visitor and
    hidden only with CSS. A dedicated public template is clearer for visitors and
    crawlers, while signed-in visitors still receive the complete dashboard unchanged.
    The previous extraction path remains as a safe fallback for incomplete deployments.
    """
    public_template = os.path.join(os.path.dirname(__file__), "templates", "public_landing.html")
    if os.path.exists(public_template):
        with open(public_template, "r", encoding="utf-8") as file:
            page = file.read()
        if "<!--RELEASE_RADAR_STRIP-->" in page:
            strip = ""
            try:
                client = getattr(request.app.state, "external_api_client", None) if request else None
                strip = release_radar.home_strip_html(client)
            except Exception:
                strip = ""  # The homepage never depends on third-party release data.
            page = page.replace("<!--RELEASE_RADAR_STRIP-->", strip, 1)
        if "<!--GUEST_PICKS-->" in page:
            try:
                from . import guest_picks
                picks_html = guest_picks.homepage_section()
            except Exception:
                picks_html = ""  # The homepage never depends on this section.
            page = page.replace("<!--GUEST_PICKS-->", picks_html, 1)
        if "<!--COMMUNITY_PROOF-->" in page:
            try:
                from . import landing_proof
                proof_html = landing_proof.homepage_section()
            except Exception:
                proof_html = ""  # The homepage never depends on this section.
            page = page.replace("<!--COMMUNITY_PROOF-->", proof_html, 1)
        return apply_site_chrome(page, login_action=True)

    landing_marker = "  <!-- Landing Page -->"
    scripts_marker = '  <script src="./credentials.js"></script>'
    body_match = re.search(r"<body[^>]*>", html, flags=re.IGNORECASE)
    landing_start = html.find(landing_marker)
    scripts_start = html.rfind(scripts_marker)

    # Keep the original page usable if a future template edit moves a marker.
    if not body_match or landing_start == -1 or scripts_start == -1 or landing_start >= scripts_start:
        return html

    public_head = html[:body_match.end()]
    public_head = public_head.replace(
        '<html lang="en">',
        '<html lang="en" data-public-shell="true">',
        1,
    )
    public_head = public_head.replace('  <script src="./preauth.js"></script>\n', "", 1)
    public_tail = html[scripts_start:].replace(
        '  <script src="./app.js"></script>',
        '  <script src="/static/public-landing.js" defer></script>',
        1,
    )
    return f"{public_head}\n{html[landing_start:scripts_start]}{public_tail}"
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_str:
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
else:
    allowed_origins = ["*"]

if ENVIRONMENT == "production" and "*" in allowed_origins:
    raise ValueError("CORS allow_origins cannot be '*' in production. Set ALLOWED_ORIGINS environment variable.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Profile pictures are now stored in the database for persistence across deployments
# Serve profile pictures from database
# Using /profile-pictures/ path to avoid conflict with /static/ mount
@app.get("/profile-pictures/{user_id}")
async def serve_profile_picture(user_id: int, db: Session = Depends(get_db)):
    """Serve profile pictures from database."""
    # Get user from database
    user = crud.get_user_by_id(db, user_id)
    if not user or not user.profile_picture_data:
        raise HTTPException(status_code=404, detail="Profile picture not found")
    
    # Return image data with appropriate MIME type
    mime_type = user.profile_picture_mime_type or "image/jpeg"
    return Response(content=user.profile_picture_data, media_type=mime_type)


@app.get("/custom-tab-posters/{item_id}")
async def serve_custom_tab_poster(
    item_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve a custom-tab poster only to the owner of that private tab."""
    item = (
        db.query(models.CustomTabItem)
        .join(models.CustomTab, models.CustomTabItem.tab_id == models.CustomTab.id)
        .filter(
            models.CustomTabItem.id == item_id,
            models.CustomTab.user_id == current_user.id,
        )
        .first()
    )
    if not item or not item.poster_data:
        raise HTTPException(status_code=404, detail="Poster not found")
    
    mime_type = item.poster_mime_type or "image/jpeg"
    return Response(content=item.poster_data, media_type=mime_type)


# Backward compatibility: support old filename-based URLs (for migration period)
# This must be registered BEFORE the static mount to take precedence
@app.get("/static/profile_pictures/{filename}")
async def serve_profile_picture_old(filename: str):
    """Backward compatibility endpoint for old profile picture URLs."""
    # Try to extract user_id from filename (format: {user_id}_{uuid}.{ext})
    match = re.match(r'^(\d+)_', filename)
    if match:
        user_id = int(match.group(1))
        # Redirect to new endpoint
        return RedirectResponse(url=f"/profile-pictures/{user_id}", status_code=301)
    raise HTTPException(status_code=404, detail="Profile picture not found")


# Mount static files for the UI
# This must be AFTER the backward compatibility route to allow it to take precedence
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Apply rate limiting to auth endpoints before including the router. FastAPI
# copies APIRoute objects during include_router(), so changing the source router
# afterward would leave the application's registered handlers unprotected.
for route in auth.router.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods') and hasattr(route, 'endpoint'):
        if route.path == "/auth/register" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("5/minute")(route.endpoint))
        elif route.path == "/auth/login" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("5/minute")(route.endpoint))
        elif route.path == "/auth/request-password-reset" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("3/hour")(route.endpoint))
        elif route.path == "/auth/resend-verification" and 'POST' in route.methods:
            bind_rate_limited_endpoint(route, limiter.limit("3/hour")(route.endpoint))

# Include routers
app.include_router(auth.router)

# Include account router and apply rate limiting to profile picture upload
from .routers.account import upload_profile_picture
rate_limited_profile_picture = limiter.limit("10/minute")(upload_profile_picture)
for route in account.router.routes:
    if hasattr(route, 'path') and route.path == "/account/profile-picture" and hasattr(route, 'methods') and 'POST' in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_profile_picture)

app.include_router(account.router)
app.include_router(friends.router)
app.include_router(notifications.router)
from .routers import library
app.include_router(library.router)
app.include_router(movies.router)
app.include_router(tv_shows.router)
app.include_router(anime.router)
app.include_router(video_games.router)
app.include_router(music.router)
app.include_router(books.router)
rate_limited_return_deck = limiter.limit("30/minute")(statistics.get_return_deck)
rate_limited_return_engagement = limiter.limit("10/minute")(statistics.record_return_deck_engagement)
for route in statistics.router.routes:
    if not hasattr(route, "path") or not hasattr(route, "methods"):
        continue
    if route.path == "/statistics/return-deck/" and "GET" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_return_deck)
    elif route.path == "/statistics/return-deck/engagement" and "POST" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_return_engagement)
app.include_router(statistics.router)
app.include_router(next_up.router)
app.include_router(completion_moments.router)
app.include_router(activity.router)
app.include_router(progress.router)
app.include_router(import_studio.router)
from .routers.recommendations import submit_public_recommendation
rate_limited_recommendation = limiter.limit("5/hour")(submit_public_recommendation)
for route in recommendations.router.routes:
    if (
        hasattr(route, "path")
        and route.path == "/recommendations/public/{token}"
        and hasattr(route, "methods")
        and "POST" in route.methods
    ):
        bind_rate_limited_endpoint(route, rate_limited_recommendation)
app.include_router(recommendations.router)
rate_limited_collection_view = limiter.limit("60/minute")(collections.public_collection)
rate_limited_collection_helpful = limiter.limit("20/hour")(collections.mark_collection_helpful)
rate_limited_collection_report = limiter.limit("2/hour")(collections.report_collection)
for route in collections.router.routes:
    if not hasattr(route, "path") or not hasattr(route, "methods"):
        continue
    if route.path == "/collections/public/{collection_id}" and "GET" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_collection_view)
    elif route.path == "/collections/public/{collection_id}/helpful" and "POST" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_collection_helpful)
    elif route.path == "/collections/public/{collection_id}/report" and "POST" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_collection_report)
app.include_router(collections.router)
app.include_router(discover.router)
app.include_router(release_radar.router)
app.include_router(export_import.router)
app.include_router(custom_tabs.router)

# Include proxy router and apply rate limiting
# We need to wrap the endpoints with rate limiting decorators
from .routers.proxy import proxy_omdb_api, proxy_rawg_api, proxy_jikan_api, proxy_itunes_api, proxy_openlibrary_api

# Create rate-limited versions
rate_limited_omdb = limiter.limit("60/minute")(proxy_omdb_api)
rate_limited_rawg = limiter.limit("60/minute")(proxy_rawg_api)
rate_limited_jikan = limiter.limit("60/minute")(proxy_jikan_api)
rate_limited_itunes = limiter.limit("60/minute")(proxy_itunes_api)
rate_limited_openlibrary = limiter.limit("60/minute")(proxy_openlibrary_api)

# Replace the endpoints in the router before including it
for route in proxy.router.routes:
    if hasattr(route, 'path') and route.path == "/api/proxy/omdb":
        bind_rate_limited_endpoint(route, rate_limited_omdb)
    elif hasattr(route, 'path') and route.path == "/api/proxy/rawg":
        bind_rate_limited_endpoint(route, rate_limited_rawg)
    elif hasattr(route, 'path') and route.path == "/api/proxy/jikan":
        bind_rate_limited_endpoint(route, rate_limited_jikan)
    elif hasattr(route, 'path') and route.path == "/api/proxy/itunes":
        bind_rate_limited_endpoint(route, rate_limited_itunes)
    elif hasattr(route, 'path') and route.path == "/api/proxy/openlibrary":
        bind_rate_limited_endpoint(route, rate_limited_openlibrary)

app.include_router(proxy.router)

app.include_router(seo.router)
app.include_router(static.router)
rate_limited_review_report = limiter.limit("2/hour")(reviews.report_public_review)
rate_limited_review_helpful = limiter.limit("30/hour")(reviews.mark_review_helpful)
for route in reviews.router.routes:
    if (getattr(route, "path", None) == "/api/public/reviews/{category}/{review_id}/helpful"
            and "POST" in getattr(route, "methods", set())):
        bind_rate_limited_endpoint(route, rate_limited_review_helpful)
for route in reviews.router.routes:
    if (
        hasattr(route, "path")
        and route.path == "/api/public/reviews/{category}/{review_id}/report"
        and hasattr(route, "methods")
        and "POST" in route.methods
    ):
        bind_rate_limited_endpoint(route, rate_limited_review_report)
app.include_router(reviews.router)
rate_limited_funnel_event = limiter.limit("30/minute")(site_stats.record_funnel_event)
for route in site_stats.router.routes:
    if getattr(route, "path", None) == "/api/funnel":
        bind_rate_limited_endpoint(route, rate_limited_funnel_event)
app.include_router(site_stats.router)
app.include_router(for_you.router)
rate_limited_guest_import = limiter.limit("10/minute")(titles.import_guest_list)
rate_limited_title_review = limiter.limit("20/minute")(titles.save_title_review)
rate_limited_take_ask = limiter.limit("20/minute")(titles.ask_for_takes)
for route in titles.router.routes:
    if getattr(route, "path", None) == "/api/guest-list/import":
        bind_rate_limited_endpoint(route, rate_limited_guest_import)
    elif getattr(route, "path", None) == "/api/titles/{kind}/{slug}/review":
        bind_rate_limited_endpoint(route, rate_limited_title_review)
    elif getattr(route, "path", None) == "/api/titles/{kind}/{slug}/ask":
        bind_rate_limited_endpoint(route, rate_limited_take_ask)
app.include_router(titles.router)

rate_limited_profile_card = limiter.limit("30/minute")(profiles.profile_card)
rate_limited_profile_card_by_id = limiter.limit("30/minute")(profiles.profile_card_by_id)
rate_limited_profile_settings = limiter.limit("20/minute")(profiles.update_profile_settings)
for route in profiles.router.routes:
    if not hasattr(route, "path") or not hasattr(route, "methods"):
        continue
    if route.path == "/u/{handle}/card.png":
        bind_rate_limited_endpoint(route, rate_limited_profile_card)
    elif route.path == "/u/id/{user_id:int}/card.png":
        bind_rate_limited_endpoint(route, rate_limited_profile_card_by_id)
    elif route.path == "/api/profile/settings" and "PUT" in route.methods:
        bind_rate_limited_endpoint(route, rate_limited_profile_settings)
app.include_router(profiles.router)
app.include_router(pwa.router)
rate_limited_kofi_webhook = limiter.limit("60/minute")(supporters.kofi_webhook)
for route in supporters.router.routes:
    if getattr(route, "path", None) == "/api/kofi/webhook" and "POST" in getattr(route, "methods", set()):
        bind_rate_limited_endpoint(route, rate_limited_kofi_webhook)
app.include_router(supporters.router)

rate_limited_recap_card = limiter.limit("30/minute")(year_in_review.shared_card)
rate_limited_own_recap_card = limiter.limit("30/minute")(year_in_review.own_card)
rate_limited_recap_share = limiter.limit("20/minute")(year_in_review.share_recap)
for route in year_in_review.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/recap/{token}/card.png":
        bind_rate_limited_endpoint(route, rate_limited_recap_card)
    elif path == "/api/year-in-review/{year}/card.png":
        bind_rate_limited_endpoint(route, rate_limited_own_recap_card)
    elif path == "/api/year-in-review/{year}/share" and "PUT" in methods:
        bind_rate_limited_endpoint(route, rate_limited_recap_share)
app.include_router(year_in_review.router)

from .routers import invites
rate_limited_invite_link = limiter.limit("20/minute")(invites.invite_link)
rate_limited_invite_accept = limiter.limit("20/minute")(invites.accept_invite)
rate_limited_join_page = limiter.limit("60/minute")(invites.join_page)
for route in invites.router.routes:
    path = getattr(route, "path", None)
    if path == "/api/friends/invite-link":
        bind_rate_limited_endpoint(route, rate_limited_invite_link)
    elif path == "/api/friends/invite/{token}/accept":
        bind_rate_limited_endpoint(route, rate_limited_invite_accept)
    elif path == "/join/{token}":
        bind_rate_limited_endpoint(route, rate_limited_join_page)
app.include_router(invites.router)

from .routers import goals as goals_router
rate_limited_goal_save = limiter.limit("30/minute")(goals_router.save_goal)
rate_limited_goal_delete = limiter.limit("30/minute")(goals_router.delete_goal)
for route in goals_router.router.routes:
    path, methods = getattr(route, "path", None), getattr(route, "methods", set())
    if path == "/api/goals/{year}/{category}" and "PUT" in methods:
        bind_rate_limited_endpoint(route, rate_limited_goal_save)
    elif path == "/api/goals/{year}/{category}" and "DELETE" in methods:
        bind_rate_limited_endpoint(route, rate_limited_goal_delete)
app.include_router(goals_router.router)


# Root endpoint
@app.get("/", tags=["root"])
@app.head("/", tags=["root"])
async def read_root(request: Request):
    # Serve the HTML UI file
    html_file = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as file:
            html = file.read()
            authenticated_shell = bool(request.cookies.get(AUTH_COOKIE_NAME))
            if not authenticated_shell:
                html = public_root_html(html, request)
                if request.method == "GET" and "token" not in request.query_params:
                    funnel.record("landing_viewed", request)
            else:
                _, dashboard_version = dashboard_assets.bundle()
                html = html.replace('src="./app.js"', f'src="./app.js?v={dashboard_version}"', 1)
                # Signed-in pages show the Friends button; drawing it from the start keeps
                # the toolbar from re-wrapping (and the page from shifting) once scripts run.
                html = html.replace('aria-controls="friendsSidebar" hidden>', 'aria-controls="friendsSidebar">', 1)
            response = nonce_html_response(html)
            response.headers["Cache-Control"] = "private, no-store" if authenticated_shell else "no-cache"
            response.headers["Vary"] = "Cookie"
            return response
    return {"message": "OmniTrackr API is running 🚀"}


@app.get("/recommend/{token}", tags=["public"])
async def recommendation_postcard_page(request: Request, token: str):
    """Serve an unindexed guest response page; the token is read by client JS."""
    response = strict_template_response("recommendation_postcard.html", request)
    if response:
        response.headers["Cache-Control"] = "no-store"
        return response
    raise HTTPException(status_code=404, detail="Recommendation Postcard page not found")


# Privacy Policy endpoint
@app.get("/privacy", tags=["public"])
async def privacy_policy(request: Request):
    """Serve the privacy policy page."""
    response = strict_template_response("privacy.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Privacy policy not found")


@app.get("/advertising", tags=["public"])
async def advertising_page(request: Request):
    response = strict_template_response("advertising.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/content-quality", tags=["public"])
async def content_quality_page(request: Request):
    response = strict_template_response("content_quality.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/site-map", tags=["public"])
async def site_map_page(request: Request):
    response = strict_template_response("site_map.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/about", tags=["public"])
async def about_page(request: Request):
    response = strict_template_response("about.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/faq", tags=["public"])
async def faq_page(request: Request):
    response = strict_template_response("faq.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/guides", tags=["public"])
async def guides_page(request: Request):
    response = strict_template_response("guides.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/compare", tags=["public"])
async def compare_page(request: Request):
    response = strict_template_response("compare.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/use-cases", tags=["public"])
async def use_cases_page(request: Request):
    response = strict_template_response("use_cases.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/changelog", tags=["public"])
async def changelog_page(request: Request):
    response = strict_template_response("changelog.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/tv-show-tracker", tags=["public"])
async def tv_show_tracker_page(request: Request):
    response = strict_template_response("tv_show_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/game-tracker", tags=["public"])
async def game_tracker_page(request: Request):
    response = strict_template_response("game_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/movie-tracker", tags=["public"])
async def movie_tracker_page(request: Request):
    response = strict_template_response("movie_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/anime-tracker", tags=["public"])
async def anime_tracker_page(request: Request):
    response = strict_template_response("anime_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/book-tracker", tags=["public"])
async def book_tracker_page(request: Request):
    response = strict_template_response("book_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/music-tracker", tags=["public"])
async def music_tracker_page(request: Request):
    response = strict_template_response("music_tracker.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/media-statistics", tags=["public"])
async def media_statistics_page(request: Request):
    response = strict_template_response("media_statistics.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/export-import-guide", tags=["public"])
async def export_import_guide_page(request: Request):
    response = strict_template_response("export_import_guide.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/media-tracker-checklist", tags=["public"])
async def media_tracker_checklist_page(request: Request):
    response = strict_template_response("media_tracker_checklist.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/tracking-templates", tags=["public"])
async def tracking_templates_page(request: Request):
    response = strict_template_response("tracking_templates.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/review-guidelines", tags=["public"])
async def review_guidelines_page(request: Request):
    response = strict_template_response("review_guidelines.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/sample-library", tags=["public"])
async def sample_library_page(request: Request):
    response = strict_template_response("sample_library.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/demo", tags=["public"])
async def demo_page(request: Request):
    response = strict_template_response("demo.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/media-tracking", tags=["public"])
async def media_tracking_page(request: Request):
    response = strict_template_response("media_tracking.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/roadmap", tags=["public"])
async def roadmap_page(request: Request):
    response = strict_template_response("roadmap.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/terms", tags=["public"])
async def terms_page(request: Request):
    response = strict_template_response("terms.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/contact", tags=["public"])
async def contact_page(request: Request):
    response = strict_template_response("contact.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


@app.get("/supporters", tags=["public"])
async def supporters_page(request: Request):
    response = strict_template_response("supporters.html", request)
    if response:
        return response
    raise HTTPException(status_code=404, detail="Page not found")


# Public endpoint for user count
@app.get("/api/user-count", response_model=schemas.UserCount, tags=["public"])
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute per IP
async def get_user_count(request: Request, db: Session = Depends(get_db)):
    """Get total number of active user accounts. Public endpoint for landing page."""
    try:
        count = db.query(models.User).filter(models.User.is_active == True).count()
        return schemas.UserCount(count=count)
    except Exception:
        # Graceful degradation: return 0 on error rather than exposing errors
        return schemas.UserCount(count=0)


# Auto-browser opening functionality
def open_browser():
    """Open the default web browser to the OmniTrackr UI"""
    import webbrowser
    import time
    import threading

    def delayed_open():
        time.sleep(2)  # Wait 2 seconds for server to start
        webbrowser.open("http://127.0.0.1:8000")

    # Start browser opening in a separate thread
    browser_thread = threading.Thread(target=delayed_open, daemon=True)
    browser_thread.start()


if __name__ == "__main__":
    import uvicorn

    open_browser()
    uvicorn.run(app, host="127.0.0.1", port=8000)
