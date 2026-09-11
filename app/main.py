"""
Entry point for the OmniTrackr API.
Provides CRUD endpoints for managing movies and TV shows.
"""
import os
import re
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from . import crud, schemas, models
from .database import Base, SessionLocal, engine
from .csp import nonce_html_response, strict_html_response
from .auth import AUTH_COOKIE_NAME
from .migrations import run_migrations
from .middleware import SecurityHeadersMiddleware, BotFilterMiddleware
from .dependencies import get_db
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
    collections,
    discover,
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Run migrations
run_migrations()

# Initialize FastAPI
app = FastAPI(title="OmniTrackr API", description="Manage your movies, TV shows, anime, video games, music, and books", version="0.1.0")

# Initialize rate limiter
if os.getenv("TESTING", "").lower() == "true":
    limiter = Limiter(key_func=lambda: "test", enabled=False)
else:
    limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
async def startup_event():
    """Run tasks on application startup."""
    try:
        db = SessionLocal()
        expired_count = crud.expire_friend_requests(db)
        if expired_count > 0:
            print(f"Expired {expired_count} old friend requests on startup")
        db.close()
    except Exception as e:
        print(f"Error expiring friend requests on startup: {e}")


# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BotFilterMiddleware)
app.add_middleware(SlowAPIMiddleware)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

AD_ELIGIBLE_TEMPLATES = {
    "about.html",
    "faq.html",
    "guides.html",
    "compare.html",
    "use_cases.html",
    "changelog.html",
    "tv_show_tracker.html",
    "game_tracker.html",
    "movie_tracker.html",
    "anime_tracker.html",
    "book_tracker.html",
    "music_tracker.html",
    "media_statistics.html",
    "export_import_guide.html",
    "media_tracker_checklist.html",
    "tracking_templates.html",
    "review_guidelines.html",
    "sample_library.html",
    "demo.html",
    "media_tracking.html",
    "roadmap.html",
    "reviews.html",
}


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


def strict_template_response(template_name: str, request: Request | None = None):
    html_file = os.path.join(os.path.dirname(__file__), "templates", template_name)
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as file:
            html = inject_adsense_account_meta(file.read())
            return strict_html_response(inject_public_ad_loader(html, template_name, request))
    return None


def public_root_html(html: str) -> str:
    """Return the standalone public landing experience without the private app shell.

    The dashboard and its empty tables used to be sent to every anonymous visitor and
    hidden only with CSS. A dedicated public template is clearer for visitors and
    crawlers, while signed-in visitors still receive the complete dashboard unchanged.
    The previous extraction path remains as a safe fallback for incomplete deployments.
    """
    public_template = os.path.join(os.path.dirname(__file__), "templates", "public_landing.html")
    if os.path.exists(public_template):
        with open(public_template, "r", encoding="utf-8") as file:
            return file.read()

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
async def serve_custom_tab_poster(item_id: int, db: Session = Depends(get_db)):
    """Serve custom tab item posters from database."""
    from . import models
    item = db.query(models.CustomTabItem).filter(models.CustomTabItem.id == item_id).first()
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


# Include routers
app.include_router(auth.router)

# Apply rate limiting to auth endpoints
for route in auth.router.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods') and hasattr(route, 'endpoint'):
        if route.path == "/auth/register" and 'POST' in route.methods:
            route.endpoint = limiter.limit("5/minute")(route.endpoint)
        elif route.path == "/auth/login" and 'POST' in route.methods:
            route.endpoint = limiter.limit("5/minute")(route.endpoint)
        elif route.path == "/auth/request-password-reset" and 'POST' in route.methods:
            route.endpoint = limiter.limit("3/hour")(route.endpoint)
        elif route.path == "/auth/resend-verification" and 'POST' in route.methods:
            route.endpoint = limiter.limit("3/hour")(route.endpoint)

# Include account router and apply rate limiting to profile picture upload
from .routers.account import upload_profile_picture
rate_limited_profile_picture = limiter.limit("10/minute")(upload_profile_picture)
for route in account.router.routes:
    if hasattr(route, 'path') and route.path == "/account/profile-picture" and hasattr(route, 'methods') and 'POST' in route.methods:
        route.endpoint = rate_limited_profile_picture

app.include_router(account.router)
app.include_router(friends.router)
app.include_router(notifications.router)
app.include_router(movies.router)
app.include_router(tv_shows.router)
app.include_router(anime.router)
app.include_router(video_games.router)
app.include_router(music.router)
app.include_router(books.router)
app.include_router(statistics.router)
app.include_router(next_up.router)
app.include_router(completion_moments.router)
app.include_router(collections.router)
app.include_router(discover.router)
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
        route.endpoint = rate_limited_omdb
    elif hasattr(route, 'path') and route.path == "/api/proxy/rawg":
        route.endpoint = rate_limited_rawg
    elif hasattr(route, 'path') and route.path == "/api/proxy/jikan":
        route.endpoint = rate_limited_jikan
    elif hasattr(route, 'path') and route.path == "/api/proxy/itunes":
        route.endpoint = rate_limited_itunes
    elif hasattr(route, 'path') and route.path == "/api/proxy/openlibrary":
        route.endpoint = rate_limited_openlibrary

app.include_router(proxy.router)

app.include_router(seo.router)
app.include_router(static.router)
app.include_router(reviews.router)


# Root endpoint
@app.get("/", tags=["root"])
@app.head("/", tags=["root"])
async def read_root(request: Request):
    # Serve the HTML UI file
    html_file = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(html_file):
        with open(html_file, "r", encoding="utf-8") as file:
            html = file.read()
            if not request.cookies.get(AUTH_COOKIE_NAME):
                html = public_root_html(html)
            return nonce_html_response(html)
    return {"message": "OmniTrackr API is running 🚀"}


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
